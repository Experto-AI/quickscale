"""SA88 cross-module migration operator-access conformance gate.

Ensures every shipped migration that executes cross-table/subquery DML
assigning ``organization_id`` does so inside a lexical
``with operator_access_migration(schema_editor)`` block.

The gate AST-parses shipped migration Python files and detects:
- Literal cross-table DML (UPDATE/INSERT/DELETE with subqueries) in
  ``schema_editor.execute()`` calls
- ORM ``.update(organization_id=...)`` writes with cross-table reads
- ``migrations.RunSQL(...)`` operations with cross-table DML
- Dynamic SQL (f-strings, ``format()``, ``%`` formatting) referencing
  ``organization_id``

Each detection requires lexical enclosure by ``operator_access_migration``
with a scope tied to the active ``schema_editor`` parameter.

Known debt exemptions are tracked in ``SA88_DEBT_EXEMPTIONS`` — an exact
file/symbol/reason ledger keyed to the owning SA issue.  Currently exempted:
- CRM 0009 ``_backfill_contactnote_org`` / ``_backfill_dealnote_org`` (ORM
  ``_base_manager`` bypasses FORCE RLS; owned by SA84 for uplift).

Comments, docstrings, DDL, and read-only SQL are ignored.

This test lives in the orgs test suite because the
``operator_access_migration`` context manager is defined in
``quickscale_modules_orgs.tenancy`` and the orgs test settings
(``--ds=tests.settings``) include all ``quickscale_modules_*`` apps,
making every shipped migration discoverable.
"""

from __future__ import annotations

import ast
import enum
import re
import sys
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path

import pytest

# BindingEvent: unified event record for any name binding within a scope.
# Fields:
#   lineno       - source line
#   col_offset   - source column (for same-line ordering)
#   kind         - binding form: canonical-import, import, import-from, import-star,
#                  param, assign, annassign, augassign, for, with_as, except,
#                  named_expr, function, class, delete, global, nonlocal
#   target       - the bound name
#   source_module - for imports, the imported module path (None otherwise)
BindingEvent = namedtuple(
    "BindingEvent",
    ["lineno", "col_offset", "kind", "target", "source_module"],
)

# Sentinel for when a local name is bound later in the function (compile-time local
# but not yet assigned at the use site).
_UNBOUND_LOCAL = "unbound-local"

# =========================================================================
# SA88a.1 Phase 1 — Abstract-domain/state primitives
# =========================================================================
# These primitives establish non-vacuous binding-state observation,
# evaluation-order transfer, and termination semantics for the operator
# access wrapper call at its exact AST evaluation point.  They build
# on the existing BindingEvent/scope-chain infrastructure and provide
# the foundation for Phase 2 (owner-cell summaries) and Phase 3
# (complete conditional construct matrix).


class BindingState(enum.Enum):
    """Binding state of a name at a specific code point.

    ``BOUND`` indicates a name is canonically bound (exact canonical import).
    ``COUNTERFEIT`` indicates the name is bound but not to the canonical
        source (assignment, non-canonical import, parameter, etc.).
    ``UNBOUND`` indicates the name is not bound in any reachable scope.
    ``UNKNOWN`` indicates the binding cannot be statically determined
        (star import, dynamic binding).
    ``DELETED`` indicates the name was explicitly deleted.
    ``MIXED`` indicates conflicting states from different predecessor paths.
    ``EMPTY`` indicates vacuous/empty state (no binding facts available).
    """

    BOUND = "bound"
    UNBOUND = "unbound"
    UNKNOWN = "unknown"
    DELETED = "deleted"
    COUNTERFEIT = "counterfeit"
    MIXED = "mixed"
    EMPTY = "empty"


class FlowExitKind(enum.Enum):
    """Exit kind for block/expression flow evaluation.

    ``NORMAL`` indicates the block fell through normally.
    ``RETURN``, ``RAISE``, ``BREAK``, ``CONTINUE`` indicate abrupt exits.
    """

    NORMAL = "normal"
    RETURN = "return"
    RAISE = "raise"
    BREAK = "break"
    CONTINUE = "continue"


@dataclass(frozen=True)
class BindingFact:
    """A fact about a name's binding state at an AST code point.

    Records the resolved binding state for *name* at the given
    ``(lineno, col_offset)``.  Canonical imports produce ``BOUND`` with
    a ``source_module``; all other binding forms produce ``COUNTERFEIT``;
    unbound names produce ``UNBOUND``; deleted names produce ``DELETED``;
    star imports and dynamic bindings produce ``UNKNOWN``.

    ``EMPTY`` state with all-default int values represents a vacuous
    binding fact — no actual binding was observed.
    """

    name: str = ""
    state: BindingState = BindingState.EMPTY
    lineno: int = 0
    col_offset: int = 0
    source_module: str | None = None

    def is_canonical(self) -> bool:
        """Return ``True`` if this fact represents a canonical binding."""
        return self.state == BindingState.BOUND and self.source_module is not None

    def is_certify(self) -> bool:
        """Return ``True`` if this fact can certify canonical consumption.

        Only BOUND canonical facts can certify.  UNKNOWN, COUNTERFEIT,
        UNBOUND, DELETED, MIXED, and EMPTY cannot certify even when the
        consumer would otherwise accept them.
        """
        return self.is_canonical()


@dataclass(frozen=True)
class FlowResult:
    """Result of evaluating a block or expression.

    Records the exit kind (how control left the evaluated region)
    and any binding facts collected during evaluation.
    """

    exit_kind: FlowExitKind = FlowExitKind.NORMAL
    facts: tuple[BindingFact, ...] = ()

    @property
    def is_abrupt(self) -> bool:
        """Return ``True`` if this result represents an abrupt exit."""
        return self.exit_kind != FlowExitKind.NORMAL

    @property
    def is_normal(self) -> bool:
        """Return ``True`` if this result represents normal completion."""
        return self.exit_kind == FlowExitKind.NORMAL


_EMPTY_FACT = BindingFact()
"""Singleton vacuous binding fact."""


_OPERATOR_ACCESS_CM_NAME = "operator_access_migration"
"""Name of the context manager function that gates must check for."""

_CANONICAL_TENANCY_MODULE = "quickscale_modules_orgs.tenancy"
"""Canonical module for operator_access_migration resolution."""

_CANONICAL_OPERATOR_ACCESS_FQN = (
    f"{_CANONICAL_TENANCY_MODULE}.{_OPERATOR_ACCESS_CM_NAME}"
)
"""Canonical fully-qualified name expected for safe operator-access access."""


# =========================================================================
# Debt exemption ledger
# =========================================================================
# Each entry is keyed by ``(app_label, migration_name)`` and contains
# exact symbol-level exemptions with a reason and owning SA issue.
# Tests prove that unlisted debt (migrations not in this ledger) FAILS
# the real-tree compliance check as a violation.
#
# When SA84 remediates the underlying issue, these exemptions can
# be removed.

SA88_DEBT_EXEMPTIONS: dict[tuple[str, str], list[dict[str, str]]] = {
    (
        "quickscale_modules_crm",
        "0009_add_note_organization_ownership",
    ): [
        {
            "symbol": "_backfill_contactnote_org",
            "category": "ungated-orm-write",
            "reason": (
                "ORM backfill — iterates objects via _base_manager and "
                "uses .update() for org assignment. The ORM-generated "
                "UPDATE is subject to FORCE RLS. If migrated to raw SQL, "
                "operator_access_migration() will be required."
            ),
            "owns": "SA84 (ORM backfill operator_access gap)",
        },
        {
            "symbol": "_backfill_dealnote_org",
            "category": "ungated-orm-write",
            "reason": (
                "ORM backfill — iterates objects via _base_manager and "
                "uses .update() for org assignment. The ORM-generated "
                "UPDATE is subject to FORCE RLS. If migrated to raw SQL, "
                "operator_access_migration() will be required."
            ),
            "owns": "SA84 (ORM backfill operator_access gap)",
        },
    ],
}


def _is_exempt_file(filepath: str | None, module_label: str | None = None) -> bool:
    """Return ``True`` if *filepath* corresponds to an exempt migration."""
    if filepath is None:
        return False
    p = Path(filepath)
    # Determine app label from the filesystem path.
    # Path example: .../crm/src/quickscale_modules_crm/migrations/0009_...
    parts = p.parts
    label: str | None = module_label
    if label is None:
        for i, part in enumerate(parts):
            if part == "src" and i + 1 < len(parts):
                label = parts[i + 1]
                break
    if label is None:
        return False
    # Match migration name: the filename without .py
    migration_name = p.stem
    return (label, migration_name) in SA88_DEBT_EXEMPTIONS


def _is_exempt_symbol(
    filepath: str | None,
    func_name: str | None,
    module_label: str | None = None,
    category: str | None = None,
) -> bool:
    """Return ``True`` if the specific function *func_name* in *filepath*
    is exempt for the given *category*.

    When a detector *category* is provided, only exemptions whose
    ``category`` field matches (or exemptions without a category field)
    are considered.  This prevents a per-category exemption from waiving
    violations of a different type in the same symbol.
    """
    if filepath is None or func_name is None:
        return False
    p = Path(filepath)
    parts = p.parts
    label: str | None = module_label
    if label is None:
        for i, part in enumerate(parts):
            if part == "src" and i + 1 < len(parts):
                label = parts[i + 1]
                break
    if label is None:
        return False
    migration_name = p.stem
    exemptions = SA88_DEBT_EXEMPTIONS.get((label, migration_name), [])
    for e in exemptions:
        if e["symbol"] != func_name:
            continue
        if category is not None and "category" in e:
            if e["category"] == category:
                return True
            continue
        return True  # Exemption without category filter matches all categories.
    return False


# =========================================================================
# AST-level helpers
# =========================================================================


def _has_subquery(upper_sql: str) -> bool:
    """Return ``True`` if *upper_sql* contains a subquery (SELECT inside
    parentheses with optional whitespace).

    This is a lexical heuristic — it does not fully parse the SQL grammar.
    It is deliberately conservative: it requires ``(`` followed (after
    optional whitespace) by ``SELECT``.
    """
    return bool(re.search(r"\(\s*SELECT\b", upper_sql))


def _is_cross_table_dml_assigning_org_id(sql_text: str) -> bool:
    """Check whether *sql_text* is a cross-table DML statement that assigns
    ``organization_id``.

    A statement is considered cross-table DML when:
    1. It is an ``UPDATE``, ``INSERT``, or ``DELETE`` statement.
    2. It contains ``ORGANIZATION_ID`` (the column being assigned).
    3. It contains a subquery (``(SELECT ...)``), OR it is an UPDATE with
       a FROM clause referencing another table, OR it is an INSERT ...
       SELECT (without enclosing parentheses around the SELECT) —
       each indicating a cross-table read that may be blocked by FORCE RLS.

    Args:
        sql_text: The SQL string literal from a ``schema_editor.execute()``
            call.

    Returns:
        ``True`` if the text matches the cross-table DML heuristic.
    """
    if not sql_text:
        return False

    stripped = sql_text.strip()
    upper = stripped.upper()

    # Must be a DML statement (UPDATE, INSERT, or DELETE).
    if not any(upper.startswith(kw) for kw in ("UPDATE ", "INSERT ", "DELETE ")):
        return False

    # Must reference organization_id (the column whose value crosses tables).
    if "ORGANIZATION_ID" not in upper:
        return False

    # --- Cross-table access checks ---

    # 1. Subquery (SELECT inside parentheses).
    if _has_subquery(upper):
        return True

    # 2. UPDATE with FROM clause referencing another table.
    if upper.startswith("UPDATE ") and " FROM " in upper:
        table_match = re.match(r"UPDATE\s+(\S+)", upper)
        from_match = re.search(r"\bFROM\s+(\S+)", upper)
        if table_match and from_match:
            update_table = table_match.group(1)
            from_table = from_match.group(1)
            # A FROM clause targeting a different table (not a parenthesised
            # subquery which is already caught above) is cross-table.
            if from_table != update_table and not from_table.startswith("("):
                return True

    # 3. INSERT INTO ... SELECT (bare SELECT, not a parenthesised subquery).
    if upper.startswith("INSERT ") and " SELECT " in upper:
        return True

    return False


def _resolve_attribute_fqn(node: ast.AST) -> str | None:
    """Resolve an AST attribute chain into a dotted FQN string.

    Supports Name/Attribute chains only.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _resolve_attribute_fqn(node.value)
        if base is None:
            return None
        return f"{base}.{node.attr}"
    return None


def _is_potential_operator_access_migration_context_expr(node: ast.AST) -> bool:
    """Return True if *node* is a candidate operator_access_migration
    context manager call site.

    This is intentionally broader than the canonical predicate and catches
    both candidate-name and attribute-based invocations, including potential
    counterfeit forms.
    """
    if isinstance(node, ast.Name):
        return node.id == _OPERATOR_ACCESS_CM_NAME
    return isinstance(node, ast.Attribute) and node.attr == _OPERATOR_ACCESS_CM_NAME


def _col_of(node: ast.AST) -> int:
    """Return col_offset with a safe default."""
    return getattr(node, "col_offset", 0)


def _lineno_of(node: ast.AST) -> int:
    """Return lineno with a safe default."""
    return getattr(node, "lineno", 0)


def _bound_name_from_import_alias(
    alias: ast.alias, is_from_import: bool = False
) -> str:
    """Return the local name bound by an import alias.

    For ``import X.Y.Z`` (``ast.Import``), the bound name is ``X`` (first
    component of the dotted path) unless ``asname`` is set.
    For ``from X import Y`` (``ast.ImportFrom``), the bound name is ``Y``
    (or ``asname``).
    """
    if alias.asname is not None:
        return alias.asname
    if is_from_import:
        return alias.name
    # ast.Import: the bound name is the top-level package name.
    return alias.name.split(".", 1)[0]


def _source_module_from_import(alias: ast.alias) -> str:
    """Return the dotted module path for a named import alias."""
    return alias.name


def _import_is_canonical_operator_access(
    node_module: str | None,
    alias: ast.alias,
) -> bool:
    """Return True if this ImportFrom alias is the exact canonical
    ``from quickscale_modules_orgs.tenancy import operator_access_migration``."""
    return (
        node_module == _CANONICAL_TENANCY_MODULE
        and alias.name == _OPERATOR_ACCESS_CM_NAME
        and alias.asname is None
    )


def _iter_binding_events(
    scope_node: ast.AST,
    target_name: str,
) -> list[BindingEvent]:
    """Collect all binding events for *target_name* in *scope_node*.

    Returns a list of ``BindingEvent`` tuples sorted by (lineno, col_offset),
    covering all binding forms: canonical-import, import, import-from,
    import-star, param, assign, annassign, augassign, for, with_as, except,
    named_expr, function, class, delete, global, nonlocal.

    Nested function/class/lambda bodies are NOT descended into, preserving
    immediate-scope semantics.
    """
    events: list[BindingEvent] = []

    # --- Function / lambda parameters ---
    if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        for arg in _iter_function_arg_nodes(scope_node):
            if arg.arg == target_name:
                events.append(
                    BindingEvent(
                        lineno=getattr(arg, "lineno", _lineno_of(scope_node)),
                        col_offset=getattr(arg, "col_offset", 0),
                        kind="param",
                        target=target_name,
                        source_module=None,
                    )
                )

    # --- Global / nonlocal declarations ---
    for node in _iter_non_nested_nodes(scope_node):
        if isinstance(node, ast.Global):
            if target_name in node.names:
                events.append(
                    BindingEvent(
                        lineno=_lineno_of(node),
                        col_offset=_col_of(node),
                        kind="global",
                        target=target_name,
                        source_module=None,
                    )
                )

        if isinstance(node, ast.Nonlocal):
            if target_name in node.names:
                events.append(
                    BindingEvent(
                        lineno=_lineno_of(node),
                        col_offset=_col_of(node),
                        kind="nonlocal",
                        target=target_name,
                        source_module=None,
                    )
                )

    # --- Statement-level binding forms ---
    for node in _iter_non_nested_nodes(scope_node):
        # Skip nested function/class/lambda definition nodes themselves
        # (their names are binding events, but we handle those below).
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
        ):
            node_name = getattr(node, "name", None)
            if node_name == target_name:
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                events.append(
                    BindingEvent(
                        lineno=_lineno_of(node),
                        col_offset=_col_of(node),
                        kind=kind,
                        target=target_name,
                        source_module=None,
                    )
                )
            continue

        # --- with ... as target ---
        if isinstance(node, ast.With):
            for item in node.items:
                if item.optional_vars is None:
                    continue
                bound_names = _extract_bound_names(item.optional_vars)
                if target_name in bound_names:
                    events.append(
                        BindingEvent(
                            lineno=_lineno_of(node),
                            col_offset=_col_of(item.optional_vars),
                            kind="with_as",
                            target=target_name,
                            source_module=None,
                        )
                    )

        # --- Plain assignment ---
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if target_name in _extract_bound_names(target):
                    events.append(
                        BindingEvent(
                            lineno=_lineno_of(target),
                            col_offset=_col_of(target),
                            kind="assign",
                            target=target_name,
                            source_module=None,
                        )
                    )

        # --- Annotated assignment ---
        if isinstance(node, ast.AnnAssign):
            if target_name in _extract_bound_names(node.target):
                events.append(
                    BindingEvent(
                        lineno=_lineno_of(node.target),
                        col_offset=_col_of(node.target),
                        kind="annassign",
                        target=target_name,
                        source_module=None,
                    )
                )

        # --- Augmented assignment ---
        if isinstance(node, ast.AugAssign):
            if target_name in _extract_bound_names(node.target):
                events.append(
                    BindingEvent(
                        lineno=_lineno_of(node.target),
                        col_offset=_col_of(node.target),
                        kind="augassign",
                        target=target_name,
                        source_module=None,
                    )
                )

        # --- Walrus operator (NamedExpr) ---
        if isinstance(node, ast.NamedExpr):
            if target_name in _extract_bound_names(node.target):
                events.append(
                    BindingEvent(
                        lineno=_lineno_of(node.target),
                        col_offset=_col_of(node.target),
                        kind="named_expr",
                        target=target_name,
                        source_module=None,
                    )
                )

        # --- For / async for target ---
        if isinstance(node, (ast.For, ast.AsyncFor)):
            if target_name in _extract_bound_names(node.target):
                events.append(
                    BindingEvent(
                        lineno=_lineno_of(node.target),
                        col_offset=_col_of(node.target),
                        kind="for",
                        target=target_name,
                        source_module=None,
                    )
                )

        # --- Except handler ---
        if isinstance(node, ast.ExceptHandler):
            if node.name == target_name:
                events.append(
                    BindingEvent(
                        lineno=_lineno_of(node),
                        col_offset=_col_of(node),
                        kind="except",
                        target=target_name,
                        source_module=None,
                    )
                )

        # --- ast.Import (``import X`` or ``import X.Y``) ---
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = _bound_name_from_import_alias(alias)
                if bound == target_name:
                    events.append(
                        BindingEvent(
                            lineno=_lineno_of(node),
                            col_offset=_col_of(node),
                            kind="import",
                            target=target_name,
                            source_module=_source_module_from_import(alias),
                        )
                    )

        # --- ast.ImportFrom (``from X import Y``) ---
        if isinstance(node, ast.ImportFrom):
            has_star = any(a.name == "*" for a in node.names)
            if has_star:
                events.append(
                    BindingEvent(
                        lineno=_lineno_of(node),
                        col_offset=_col_of(node),
                        kind="import-star",
                        target=target_name,
                        source_module=node.module,
                    )
                )
                # Star import affects ALL names; continue to check specific aliases
                # because an exact import on the same line would override.

            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = _bound_name_from_import_alias(alias, is_from_import=True)
                if bound != target_name:
                    continue

                if _import_is_canonical_operator_access(node.module, alias):
                    events.append(
                        BindingEvent(
                            lineno=_lineno_of(node),
                            col_offset=_col_of(node),
                            kind="canonical-import",
                            target=target_name,
                            source_module=node.module,
                        )
                    )
                else:
                    events.append(
                        BindingEvent(
                            lineno=_lineno_of(node),
                            col_offset=_col_of(node),
                            kind="import-from",
                            target=target_name,
                            source_module=node.module,
                        )
                    )

        # --- Delete ---
        if isinstance(node, ast.Delete):
            for target in node.targets:
                if target_name in _extract_bound_names(target):
                    events.append(
                        BindingEvent(
                            lineno=_lineno_of(target),
                            col_offset=_col_of(target),
                            kind="delete",
                            target=target_name,
                            source_module=None,
                        )
                    )

    # Sort by (lineno, col_offset) for stable source-order semantics.
    events.sort(key=lambda e: (e.lineno, e.col_offset))
    return events


def _scope_chain_for_operator_access_call(
    tree: ast.AST,
    lineno: int,
) -> list[ast.AST]:
    """Return outer-to-inner scope chain for *lineno* in *tree*.

    The chain always starts with tree (module scope), followed by any
    enclosing function scopes containing *lineno*.
    """
    chain: list[ast.AST] = [tree]
    nested_funcs: list[ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda] = []
    for node in _iter_function_nodes(tree):
        start = node.lineno
        end = node.end_lineno or start
        if start <= lineno <= end:
            nested_funcs.append(node)
    nested_funcs.sort(key=lambda f: f.lineno)
    chain.extend(nested_funcs)
    return chain


def _resolve_active_binding(
    tree: ast.AST,
    lineno: int,
    col_offset: int,
    target_name: str,
    scope_chain: list[ast.AST] | None = None,
) -> BindingEvent | None:
    """Scope-chain-aware resolution of the active binding for *target_name*.

    Walks the scope chain from innermost to outermost, applying:

    * **Module-scope (global) rule**: Uses the *last* (by lineno, col_offset)
      binding in module scope because all module-level statements execute
      before any migration callback runs.

    * **LEGB order**: Iterates from innermost to outermost enclosing scope.
      The first scope that has a local binding wins.

    * **Function-scope compile-time-local rule**: If a name is bound ANYWHERE
      in a function (any binding form except ``global``/``nonlocal``), it is
      local to that function at compile time.  A use before any such binding
      does NOT fall through to an outer scope — the active binding is returned
      as kind ``"unbound-local"``.

    * **``global`` / ``nonlocal``**: A ``global`` declaration makes the name
      resolve to module scope; ``nonlocal`` makes it resolve to the nearest
      enclosing function scope.

    * **Source-order**: Within a scope, the most recent binding by
      (lineno, col_offset) before the call site is used.

    Returns a ``BindingEvent`` or ``None`` (unbound in all reachable scopes).
    """
    chain = scope_chain or _scope_chain_for_operator_access_call(tree, lineno)
    call_key = (lineno, col_offset)

    for depth in range(len(chain) - 1, -1, -1):
        scope_node = chain[depth]
        is_module = isinstance(scope_node, ast.Module)
        events = _iter_binding_events(scope_node, target_name)

        if not events:
            continue  # No binding in this scope — fall through.

        if is_module:
            # Module-final: the last binding by source order.
            return events[-1]

        # --- Function / class scope ---

        # Separate global/nonlocal declarations from real bindings.
        real_bindings = [e for e in events if e.kind not in ("global", "nonlocal")]
        has_global = any(e.kind == "global" for e in events)
        has_nonlocal = any(e.kind == "nonlocal" for e in events)

        if has_global:
            # ``global target_name`` — the name resolves to module scope.
            # Continue to the next outer scope in the chain.
            # (If we're already at module scope, this shouldn't happen,
            # but guard against it.)
            if depth == 0:
                return None
            continue

        if has_nonlocal:
            # ``nonlocal target_name`` — the name resolves to the nearest
            # enclosing function scope (skip this one).
            # Find the next outer function scope.
            outer_depth = depth - 1
            while outer_depth >= 0:
                outer = chain[outer_depth]
                if isinstance(
                    outer,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda),
                ):
                    break
                outer_depth -= 1
            if outer_depth < 0:
                # nonlocal at module level — should not happen in valid code,
                # but fall through safely.
                continue
            # Skip this scope; the loop will continue to outer scopes
            # (we've already determined that the module case handles last).
            # BUT: we need the loop to actually find the outer scope.
            # The natural fall-through handles this; continue to next depth.
            continue

        if not real_bindings:
            continue  # Only global/nonlocal — name not actually bound here.

        # Name is bound somewhere in this function → COMPILE-TIME LOCAL.
        # Find the most recent binding before the call site.
        before = [e for e in real_bindings if (e.lineno, e.col_offset) <= call_key]
        if not before:
            # All bindings are after the use site — still local, but unbound.
            return BindingEvent(
                lineno=lineno,
                col_offset=col_offset,
                kind=_UNBOUND_LOCAL,
                target=target_name,
                source_module=None,
            )

        # Return the most recent binding by source order.
        return before[-1]

    return None


def _is_func_called_before_in_scope(
    scope_body: list[ast.AST],
    func_name: str,
    target_lineno: int,
) -> bool:
    """Return ``True`` if *func_name* is called by name as a direct
    ``Expr(Call(Name(func_name), ...))`` statement in *scope_body* at a
    line before *target_lineno*.

    Recursively descends into if/while/for/try bodies to capture calls
    in compound statements.  Nested function/class/lambda definitions
    are NOT descended into (their bodies are not part of the enclosing
    execution flow).  Calls in comprehension/generator expressions are
    also excluded.

    When *target_lineno* falls inside a nested function definition in
    *scope_body*, the enclosing scope's call statements execute AFTER
    all nested definitions but still BEFORE the nested function body.
    In that case the cutoff is lifted to scan the entire scope body.
    """
    cutoff = target_lineno
    for stmt in scope_body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        s_start = stmt.lineno
        s_end = stmt.end_lineno or s_start
        if s_start <= target_lineno <= s_end:
            cutoff = sys.maxsize
            break

    for stmt in scope_body:
        stmt_lineno = getattr(stmt, "lineno", 0)
        if stmt_lineno >= cutoff:
            break

        # Skip nested definitions.
        if isinstance(
            stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue

        # Direct Expr(Call(Name(func_name), ...))
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if isinstance(call.func, ast.Name) and call.func.id == func_name:
                return True
            if isinstance(call.func, ast.Attribute) and call.func.attr == func_name:
                return True

        # Recurse into compound statements.
        if isinstance(stmt, ast.If):
            if _is_func_called_before_in_scope(stmt.body, func_name, target_lineno):
                return True
            if _is_func_called_before_in_scope(stmt.orelse, func_name, target_lineno):
                return True
        if isinstance(stmt, ast.Try):
            if _is_func_called_before_in_scope(stmt.body, func_name, target_lineno):
                return True
            for h in stmt.handlers:
                if _is_func_called_before_in_scope(h.body, func_name, target_lineno):
                    return True
            if _is_func_called_before_in_scope(stmt.orelse, func_name, target_lineno):
                return True
            if _is_func_called_before_in_scope(
                stmt.finalbody, func_name, target_lineno
            ):
                return True
        if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            if _is_func_called_before_in_scope(stmt.body, func_name, target_lineno):
                return True
            if _is_func_called_before_in_scope(stmt.orelse, func_name, target_lineno):
                return True
        if isinstance(stmt, ast.With):
            if _is_func_called_before_in_scope(stmt.body, func_name, target_lineno):
                return True

    return False


def _resolve_owner_aware_binding(
    tree: ast.AST,
    lineno: int,
    col_offset: int,
    target_name: str,
    scope_chain: list[ast.AST] | None = None,
) -> BindingEvent | None:
    """Phase 2 owner-aware binding resolution.

    Like :func:`_resolve_active_binding` but accounts for ``global``
    and ``nonlocal`` declarations that redirect assignments to their
    owner cells rather than creating local bindings.

    **Call-order-aware mutation model**: A global/nonlocal mutation in a
    nested or sibling function takes effect ONLY when that function is
    actually CALLED before the target call site in the enclosing scope.
    Functions that are only defined (never called) do NOT transfer their
    mutations.  When call order cannot be determined, the function
    conservatively falls through to the normal lexical resolution.

    Direct bindings (assignments, imports) in the same function body as
    the call site are handled by ``_resolve_active_binding``.

    Returns a ``BindingEvent`` with the effective kind after owner-cell
    resolution, or ``None`` when unbound.
    """
    chain = scope_chain or _scope_chain_for_operator_access_call(tree, lineno)
    normal = _resolve_active_binding(tree, lineno, col_offset, target_name, chain)

    def _find_effective_global_mutations(
        scope_node: ast.AST, scope_body: list[ast.AST] | None
    ) -> list[tuple[BindingEvent, ast.AST]]:
        """Return (event, func_node) for each real binding in a
        function defined in *scope_node* that has ``global target_name``
        AND is called before *lineno* in *scope_body*."""
        results: list[tuple[BindingEvent, ast.AST]] = []
        if scope_body is not None:
            for stmt in scope_body:
                if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if stmt.lineno >= lineno:
                    continue
                fevents = _iter_binding_events(stmt, target_name)
                if any(e.kind == "global" for e in fevents):
                    real = [e for e in fevents if e.kind not in ("global", "nonlocal")]
                    if real and _is_func_called_before_in_scope(
                        scope_body, stmt.name, lineno
                    ):
                        for e in real:
                            results.append((e, stmt))
        return results

    def _find_effective_nonlocal_mutations(
        scope_node: ast.AST,
        scope_body: list[ast.AST] | None,
    ) -> list[tuple[BindingEvent, ast.AST]]:
        """Same for ``nonlocal``."""
        results: list[tuple[BindingEvent, ast.AST]] = []
        if scope_body is not None:
            for stmt in scope_body:
                if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if stmt.lineno >= lineno:
                    continue
                fevents = _iter_binding_events(stmt, target_name)
                if any(e.kind == "nonlocal" for e in fevents):
                    real = [e for e in fevents if e.kind not in ("global", "nonlocal")]
                    if real and _is_func_called_before_in_scope(
                        scope_body, stmt.name, lineno
                    ):
                        results.append((e, stmt))
        return results

    # --- Step 1: Global mutations ---
    global_mutations: list[tuple[BindingEvent, ast.AST]] = []
    for depth in range(len(chain)):
        scope = chain[depth]
        scope_body = getattr(scope, "body", None)
        for e, func_node in _find_effective_global_mutations(scope, scope_body):
            global_mutations.append((e, func_node))

    if global_mutations:
        best_gm = max(
            global_mutations, key=lambda item: (item[0].lineno, item[0].col_offset)
        )
        best_gm_event, _ = best_gm
        normal_at_module = False
        if normal is not None:
            mod_events = _iter_binding_events(chain[0], target_name)
            normal_at_module = any(
                e.lineno == normal.lineno and e.col_offset == normal.col_offset
                for e in mod_events
            )
        else:
            normal_at_module = True

        if normal_at_module:
            if normal is None or (
                best_gm_event.lineno,
                best_gm_event.col_offset,
            ) > (normal.lineno, normal.col_offset):
                return best_gm_event

    # --- Step 2: Nonlocal mutations ---
    nonlocal_mutations: list[tuple[BindingEvent, ast.AST, int]] = []
    for depth in range(len(chain)):
        scope = chain[depth]
        scope_body = getattr(scope, "body", None)
        for e, func_node in _find_effective_nonlocal_mutations(scope, scope_body):
            target_depth: int | None = None
            for td in range(depth + 1, len(chain)):
                ts = chain[td]
                if not isinstance(ts, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                te = _iter_binding_events(ts, target_name)
                if any(e.kind not in ("global", "nonlocal") for e in te):
                    target_depth = td
                    break
            if target_depth is None:
                for td in range(len(chain) - 1, -1, -1):
                    if isinstance(chain[td], (ast.FunctionDef, ast.AsyncFunctionDef)):
                        target_depth = td
                        break
            if target_depth is not None:
                nonlocal_mutations.append((e, func_node, target_depth))

    if nonlocal_mutations and normal is not None:
        nonlocal_mutations.sort(
            key=lambda item: (
                item[1].lineno,
                getattr(item[1], "col_offset", 0),
                item[0].lineno,
            ),
        )
        best_nl, nl_func, nl_target_depth = nonlocal_mutations[-1]
        if nl_target_depth < len(chain):
            target_scope = chain[nl_target_depth]
            target_events = _iter_binding_events(target_scope, target_name)
            normal_in_target = any(
                e.lineno == normal.lineno and e.col_offset == normal.col_offset
                for e in target_events
            )
            if normal_in_target:
                if (nl_func.lineno, getattr(nl_func, "col_offset", 0)) > (
                    normal.lineno,
                    normal.col_offset,
                ):
                    return best_nl

    return normal


# =========================================================================
# SA88a.1 Phase 3 — Reaching-state / path-sensitive transfer
# =========================================================================
# These helpers extend the binding resolution with path-sensitive
# reaching-state analysis across conditional constructs (if/else,
# loops, try/except, match, comprehension, with).  A binding is
# canonical only when EVERY live reaching path provides a canonical
# fact; empty/unbound/unknown/deleted/counterfeit/mixed fail closed.


def _binding_event_to_state(event: BindingEvent) -> BindingState:
    """Map a ``BindingEvent`` to the corresponding ``BindingState``."""
    if event is None:
        return BindingState.UNBOUND
    if event.kind == "canonical-import":
        return BindingState.BOUND
    if event.kind == "delete":
        return BindingState.DELETED
    if event.kind in ("import-star",):
        return BindingState.UNKNOWN
    if event.kind == _UNBOUND_LOCAL:
        return BindingState.UNBOUND
    # Canonical root module import: ``import quickscale_modules_orgs``
    # or ``import quickscale_modules_orgs.tenancy``.
    if event.kind == "import" and event.source_module is not None:
        if event.source_module.split(".", 1)[0] == "quickscale_modules_orgs":
            return BindingState.BOUND
    return BindingState.COUNTERFEIT


def _merge_states(states: list[BindingState]) -> BindingState:
    """Merge a list of ``BindingState`` values from parallel paths.

    ``BOUND`` only when EVERY path agrees on ``BOUND``.
    ``MIXED`` when any combination of non-identical states appears.
    """
    if not states:
        return BindingState.EMPTY
    unique = set(states)
    if len(unique) == 1:
        return unique.pop()
    # Multiple distinct states → mixed (cannot certify)
    return BindingState.MIXED


def _statements_reach_line(
    body: list[ast.AST],
    target_lineno: int,
    target_name: str,
    initial_state: BindingState | None = None,
) -> BindingState | None:
    """Walk *body* statements tracking reaching state of *target_name*
    up to *target_lineno*.

    *initial_state* is the state entering the body (for example the
    module-level state before the function body).  Returns ``None``
    if the target line is not reached (all paths terminate before it),
    or a ``BindingState`` representing the merged reaching state
    across all live paths.

    For unconditional bindings at the top level of *body*:
    the state is updated directly (module-final semantics within
    the body).

    For conditional constructs (if/else, for/while, try/except,
    match, with) the state is merged across branches.
    """
    current_state: BindingState | None = initial_state

    for stmt in body:
        stmt_lineno = getattr(stmt, "lineno", 0)
        if stmt_lineno >= target_lineno:
            return current_state

        # Skip nested function/class/lambda — their internal
        # bindings do not affect the outer scope's reaching state.
        if isinstance(
            stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue

        # --- Unconditional binding detection ---
        # These statements bind *target_name* unconditionally at
        # the top level of this body.

        # Import / ImportFrom
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                bound = _bound_name_from_import_alias(alias)
                if bound == target_name:
                    events = _iter_binding_events(
                        ast.Module(body=[stmt], type_ignores=[]), target_name
                    )
                    if events:
                        current_state = _binding_event_to_state(events[-1])

        if isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                bound = _bound_name_from_import_alias(alias, is_from_import=True)
                if bound == target_name:
                    events = _iter_binding_events(
                        ast.Module(body=[stmt], type_ignores=[]), target_name
                    )
                    if events:
                        current_state = _binding_event_to_state(events[-1])

        # Assignment targets
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if target_name in _extract_bound_names(target):
                    current_state = BindingState.COUNTERFEIT

        if isinstance(stmt, ast.AnnAssign):
            if target_name in _extract_bound_names(stmt.target):
                current_state = BindingState.COUNTERFEIT

        if isinstance(stmt, ast.AugAssign):
            if target_name in _extract_bound_names(stmt.target):
                current_state = BindingState.COUNTERFEIT

        if isinstance(stmt, ast.NamedExpr):
            if target_name in _extract_bound_names(stmt.target):
                current_state = BindingState.COUNTERFEIT

        # Function/class definition
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if stmt.name == target_name:
                current_state = BindingState.COUNTERFEIT
        if isinstance(stmt, ast.ClassDef):
            if stmt.name == target_name:
                current_state = BindingState.COUNTERFEIT

        # For/AsyncFor target — unconditional binding of loop var
        if isinstance(stmt, (ast.For, ast.AsyncFor)):
            if target_name in _extract_bound_names(stmt.target):
                current_state = BindingState.COUNTERFEIT

        # --- Check for NamedExpr across the entire statement ---
        # This catches walrus operators inside comprehensions, if-test
        # expressions, argument lists, etc.
        if isinstance(
            stmt,
            (
                ast.If,
                ast.While,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
            ),
        ):
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.NamedExpr):
                    if target_name in _extract_bound_names(sub.target):
                        if current_state is None:
                            current_state = BindingState.UNKNOWN
                        else:
                            current_state = BindingState.MIXED

        # --- if / elif / else ---
        if isinstance(stmt, ast.If):
            # Seed both branches with current predecessor state.
            if_state = _statements_reach_line(
                stmt.body, target_lineno, target_name, current_state
            )
            else_body: list[ast.AST] = []
            for orelse_node in stmt.orelse:
                if isinstance(orelse_node, ast.If):
                    else_body.append(orelse_node)
                else:
                    else_body = stmt.orelse
                    break

            # Empty else body (no else clause) → implicit fallthrough
            # inherits the predecessor state.
            if not else_body:
                else_state = current_state
            else:
                else_state = _statements_reach_line(
                    else_body, target_lineno, target_name, current_state
                )

            # Collect live-path states.  None means all paths through that
            # branch terminate before the target — no state contribution.
            branch_states: list[BindingState] = []
            if if_state is not None:
                branch_states.append(if_state)
            if else_state is not None:
                branch_states.append(else_state)

            if not branch_states:
                # Both branches terminate before target → no live path
                return None

            # Merge all live-path states.  BOUND only when EVERY live
            # path agrees on BOUND.
            current_state = _merge_states(branch_states)
            continue

        # --- for / while loop ---
        if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            pre_loop = current_state
            body_state = _statements_reach_line(
                stmt.body, target_lineno, target_name, pre_loop
            )
            if body_state is None:
                # All paths in body terminate before target.
                # Loop might not execute → pre_loop state is live
                continue
            if body_state != pre_loop:
                # Loop body changes the binding.  Since the loop might
                # execute zero times, the reaching state is UNKNOWN.
                current_state = BindingState.UNKNOWN
            # else body_state == pre_loop: loop body doesn't change
            # the binding; pre_loop state is preserved.
            continue

        # --- try / except / else / finally ---
        if isinstance(stmt, ast.Try):
            # Try body: seeded with current predecessor state.
            try_state = _statements_reach_line(
                stmt.body, target_lineno, target_name, current_state
            )

            # Handlers and else execute AFTER the try body.  If the try
            # body makes binding changes before raising, the handlers
            # must see that modified state.  Use try_state as the initial
            # state for handlers and else; if try_state is None (try body
            # paths all terminate before target), fall back to predecessor.
            handler_initial = try_state if try_state is not None else current_state
            handler_states: list[BindingState] = []
            for handler in stmt.handlers:
                hs = _statements_reach_line(
                    handler.body, target_lineno, target_name, handler_initial
                )
                if hs is not None:
                    handler_states.append(hs)

            else_try_state = _statements_reach_line(
                stmt.orelse, target_lineno, target_name, handler_initial
            )

            # Collect live-path states from try/except/else.
            # If the try body has an unconditional abrupt exit (return or
            # raise at the top level), its state should NOT be merged as a
            # live post-try path — the exception/handler flow replaces it.
            # The try body state only serves as the initial state for
            # handlers (handled above via handler_initial).
            # Similarly, the else block never executes when the try body
            # raises — exclude its state when the try body has an abrupt exit.
            _try_body_has_abrupt = any(
                isinstance(s, (ast.Raise, ast.Return)) for s in stmt.body
            )
            all_try_states: list[BindingState] = []
            if try_state is not None and not _try_body_has_abrupt:
                all_try_states.append(try_state)
            if handler_states:
                all_try_states.extend(handler_states)
            if else_try_state is not None and not _try_body_has_abrupt:
                all_try_states.append(else_try_state)

            if all_try_states:
                current_state = _merge_states(all_try_states)
            elif current_state is not None:
                # All try/except/else paths terminate before target.
                return None

            # Finally runs on EVERY exit path.  Its bindings are
            # guaranteed to apply after the merged try/except/else
            # state, on ANY live path that reaches the target.
            if stmt.finalbody:
                finally_state = _statements_reach_line(
                    stmt.finalbody, target_lineno, target_name, current_state
                )
                if finally_state is not None:
                    current_state = finally_state
                elif current_state is not None:
                    # Finally body terminates before target → no live path.
                    return None

            continue

        # --- with ---
        if isinstance(stmt, ast.With):
            with_state = _statements_reach_line(stmt.body, target_lineno, target_name)
            if with_state is not None and with_state != current_state:
                current_state = with_state
            # If with_state is None (all paths in body terminate),
            # the rest is dead
            elif with_state is None and current_state is not None:
                # Check if any termination is before target
                if not _block_has_live_path_to(stmt.body, target_lineno):
                    pass  # body terminates, but with may have exit
                return None
            continue

        # --- match ---
        if isinstance(stmt, ast.Match):
            case_state_list: list[BindingState] = []
            for case in stmt.cases:
                cs = _statements_reach_line(case.body, target_lineno, target_name)
                if cs is not None:
                    case_state_list.append(cs)
            if case_state_list:
                current_state = _merge_states(case_state_list)
            # If no case reaches, the target is dead
            # (match fails closed at runtime with no default)
            continue

    return current_state


def _resolve_reaching_state(
    tree: ast.AST,
    lineno: int,
    col_offset: int,
    target_name: str,
    scope_chain: list[ast.AST] | None = None,
) -> BindingState:
    """Phase 3: resolve the path-sensitive reaching state of
    *target_name* at ``(lineno, col_offset)``.

    Returns ``BindingState.BOUND`` only when EVERY live reaching path
    provides a canonical binding.  All other cases return the
    appropriate non-canonical state.

    This wraps ``_resolve_owner_aware_binding`` with the body-walking
    reaching-state analysis to detect cases where a canonical-looking
    binding is conditionally overridden on some paths (e.g. inside
    an if/else branch, a loop body, a try handler, etc.).
    """
    chain = scope_chain or _scope_chain_for_operator_access_call(tree, lineno)

    # Walk ALL module-level statements including those after function
    # definitions (late rebindings).  Use sys.maxsize as the target line
    # so that _statements_reach_line never truncates early; it already
    # skips nested function/class/lambda bodies via its unconditional
    # detection skip logic.
    state = (
        _statements_reach_line(
            chain[0].body,
            sys.maxsize,
            target_name,
            BindingState.UNBOUND,
        )
        or BindingState.UNBOUND
    )

    # Walk each function scope in the chain.  If the scope has a
    # compile-time local binding of *target_name*, the module state
    # is shadowed — pass None as initial state.  Otherwise pass the
    # current state (which may come from module scope).
    for depth in range(1, len(chain)):
        scope = chain[depth]
        if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        body = getattr(scope, "body", [])
        # Check if this scope has a compile-time local binding.
        events = _iter_binding_events(scope, target_name)
        has_local = any(e.kind not in ("global", "nonlocal") for e in events)
        initial = None if has_local else state
        body_state = _statements_reach_line(body, lineno, target_name, initial)
        if body_state is not None:
            state = body_state
        elif has_local:
            # Scope has compile-time local but all paths terminate.
            state = BindingState.UNKNOWN

    return state


def _is_canonical_on_all_paths(
    tree: ast.AST,
    lineno: int,
    col_offset: int,
    target_name: str,
    scope_chain: list[ast.AST] | None = None,
) -> bool:
    """Phase 3: return ``True`` if *target_name* is canonically bound
    on EVERY live reaching path at ``(lineno, col_offset)``.

    Combines the Phase 2 owner-aware resolution with Phase 3
    path-sensitive reaching-state analysis.
    """
    reaching = _resolve_reaching_state(
        tree, lineno, col_offset, target_name, scope_chain
    )
    return reaching == BindingState.BOUND


def _is_root_canonically_bound(
    tree: ast.AST,
    lineno: int,
    col_offset: int,
    scope_chain: list[ast.AST] | None = None,
) -> bool:
    """Return ``True`` if ``quickscale_modules_orgs`` is canonically bound
    on EVERY live reaching path at (lineno, col_offset).

    A canonical root binding is ``import quickscale_modules_orgs`` or
    ``import quickscale_modules_orgs.tenancy`` (an ``ast.Import`` node where
    the imported module starts with ``quickscale_modules_orgs``).

    All other binding forms (ImportFrom, assignment, parameter, function
    definition, class definition, for/with/except target, import-as alias)
    make the root counterfeit or unbound.

    Uses Phase 2 owner-aware resolution plus Phase 3 path-sensitive
    reaching-state analysis.
    """
    active = _resolve_owner_aware_binding(
        tree, lineno, col_offset, "quickscale_modules_orgs", scope_chain
    )
    if active is None:
        return False  # Unbound — not canonical.

    if active.kind == "import" and active.source_module is not None:
        # The single-binding check passes.  Now verify path-sensitivity.
        return _is_canonical_on_all_paths(
            tree, lineno, col_offset, "quickscale_modules_orgs", scope_chain
        )

    # All other binding forms (import-from, param, assign, function, class,
    # for, with_as, except, named_expr, unbound-local, delete, star, etc.)
    # are counterfeit or non-canonical.
    return False


def _is_operator_access_migration_call(
    node: ast.AST,
    tree: ast.AST | None = None,
    scope_chain: list[ast.AST] | None = None,
    lineno: int | None = None,
) -> bool:
    """Return True if *node* is a canonical operator-access context call.

    Canonical calls are:
    1. exact attribute FQN quickscale_modules_orgs.tenancy.operator_access_migration
       where the root name is canonically bound (scope-chain-aware).
    2. direct operator_access_migration name bound by
       from quickscale_modules_orgs.tenancy import operator_access_migration
       with no alias in scope.

    Uses the unified ``_consume_canonical`` predicate so wrapper
    collection, Detector 7, and Phase 1/2 tests share one code path.
    """
    if not isinstance(node, ast.Call):
        return False
    if tree is None:
        return False

    # Delegate to the unified canonical consumption predicate, which
    # handles both FQN and bare-name forms via _observe_call_fact.
    return _consume_canonical(tree, node, scope_chain=scope_chain)


def _find_operator_access_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    """Find ``(start_line, end_line)`` for every canonical
    ``with operator_access_migration(...)`` block in *tree*.

    Returns a list of inclusive line-number ranges.
    """
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            chain = _scope_chain_for_operator_access_call(tree, node.lineno)
            for item in node.items:
                if _is_operator_access_migration_call(
                    item.context_expr,
                    tree=tree,
                    scope_chain=chain,
                    lineno=node.lineno,
                ):
                    # end_lineno is available in Python 3.8+.
                    end_lineno = node.end_lineno
                    end = end_lineno if end_lineno is not None else node.lineno
                    ranges.append((node.lineno, end))
    return ranges


def _is_within_ranges(lineno: int, ranges: list[tuple[int, int]]) -> bool:
    """Return ``True`` if *lineno* falls within any ``(start, end)`` range."""
    return any(start <= lineno <= end for start, end in ranges)


def _extract_sql_arg(call_node: ast.Call) -> str | None:
    """Extract the SQL string from the first argument of
    ``schema_editor.execute(...)`` (or ``cursor.execute(...)``).

    Returns the string value, or ``None`` if it cannot be statically
    determined (e.g. a variable or expression).
    """
    if not call_node.args:
        return None
    first_arg = call_node.args[0]
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        return first_arg.value
    return None


def _is_execute_call(node: ast.AST) -> bool:
    """Return ``True`` if *node* is a method call named ``execute()``.

    Matches ``name.execute(...)`` for any simple name (e.g.
    ``schema_editor.execute(...)``, ``cursor.execute(...)``,
    ``cur.execute(...)``).
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    )


# =========================================================================
# Detector: ORM .update(organization_id=...) writes
# =========================================================================


def _is_orm_update_write(node: ast.AST) -> bool:
    """Return ``True`` if *node* is an ORM ``.update(organization_id=...)``
    call that assigns ``organization_id`` as a keyword argument.

    Matches patterns like:
    - ``MyModel._base_manager.filter(...).update(organization_id=...)``
    - ``MyModel.objects.update(organization_id=...)``
    - ``Manager.objects.filter(pk=...).update(organization_id=...)``

    This detects cross-table ORM writes that go through the ORM's
    SQL generation but still produce UPDATE statements referencing
    ``organization_id``.
    """
    if not isinstance(node, ast.Call):
        return False
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr != "update":
        return False
    # Check whether organization_id appears as a keyword argument.
    for kw in node.keywords:
        if kw.arg == "organization_id":
            return True
    return False


# =========================================================================
# Detector: migrations.RunSQL operations
# =========================================================================


def _is_runsql_dml_call(node: ast.AST) -> bool:
    """Return ``True`` if *node* is a ``migrations.RunSQL(...)`` call
    that might contain cross-table DML.

    Matches ``RunSQL(sql, ...)`` where ``sql`` is a string constant
    or tuple of string constants.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # migrations.RunSQL or RunSQL (after from-import)
    if isinstance(func, ast.Attribute) and func.attr == "RunSQL":
        pass  # Likely migrations.RunSQL
    elif isinstance(func, ast.Name) and func.id == "RunSQL":
        pass  # from-import case
    else:
        return False
    return True


def _extract_runsql_sql(call_node: ast.Call) -> list[str]:
    """Extract SQL string(s) from a ``migrations.RunSQL(...)`` call.

    Returns a list of SQL strings (possibly empty).
    """
    if not call_node.args:
        return []
    first_arg = call_node.args[0]
    results: list[str] = []
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        results.append(first_arg.value)
    elif isinstance(first_arg, ast.Tuple):
        for elt in first_arg.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                results.append(elt.value)
    return results


# =========================================================================
# Detector: dynamic SQL (f-strings, format(), %)
# =========================================================================


def _is_dynamic_sql_with_org_id(node: ast.AST) -> bool:
    """Return ``True`` if *node* is an ``execute()`` call whose SQL
    argument is dynamically constructed (f-string, ``format()`` call,
    ``%`` operator) and contains ``organization_id``.

    Dynamic SQL cannot be statically analysed, so we flag it as a
    manual-review item when ``organization_id`` appears in the
    template/format string.
    """
    if not isinstance(node, ast.Call):
        return False
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "execute":
        return False
    if not node.args:
        return False
    first_arg = node.args[0]
    # f-string (ast.JoinedStr)
    if isinstance(first_arg, ast.JoinedStr):
        # Get the first constant part to determine if SQL is DML or DDL/read-only.
        first_const = ""
        for value in first_arg.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                first_const = value.value.upper()
                break
        if not first_const:
            return False
        # Only flag if the SQL starts with a DML keyword (UPDATE, INSERT, DELETE).
        # Use the full string including trailing space for matching.
        if not any(
            first_const.startswith(kw) for kw in ("UPDATE ", "INSERT ", "DELETE ")
        ):
            return False
        # Check for ORGANIZATION_ID reference in any constant part.
        for value in first_arg.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                if "ORGANIZATION_ID" in value.value.upper():
                    return True
        return False
    # format() call: "..." % value
    if isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, ast.Mod):
        if isinstance(first_arg.left, ast.Constant) and isinstance(
            first_arg.left.value, str
        ):
            upper = first_arg.left.value.strip().upper()
            if not any(
                upper.startswith(kw) for kw in ("UPDATE ", "INSERT ", "DELETE ")
            ):
                return False
            if "ORGANIZATION_ID" in upper:
                return True
        return False
    # .format() call
    if isinstance(first_arg, ast.Call) and isinstance(first_arg.func, ast.Attribute):
        if first_arg.func.attr == "format":
            if first_arg.func.value and isinstance(first_arg.func.value, ast.Constant):
                if isinstance(first_arg.func.value.value, str):
                    upper = first_arg.func.value.value.strip().upper()
                    if not any(
                        upper.startswith(kw) for kw in ("UPDATE ", "INSERT ", "DELETE ")
                    ):
                        return False
                    if "ORGANIZATION_ID" in upper:
                        return True
        return False
    return False


# =========================================================================
# Detector: raw GUC manipulation (SET/SET LOCAL/RESET/set_config)
# =========================================================================
# These are non-exemptible: direct GUC manipulation is always a violation
# even when inside an operator_access_migration block, because the context
# manager is the only permitted mechanism.


_RAW_GUC_PATTERNS: list[re.Pattern] = [
    re.compile(r"SET\s+LOCAL\s+app\.operator_access\s*=", re.IGNORECASE),
    re.compile(r"SET\s+(SESSION\s+)?app\.operator_access\s*=", re.IGNORECASE),
    re.compile(r"RESET\s+app\.operator_access\b", re.IGNORECASE),
    re.compile(
        r"set_config\s*\(\s*['\"]app\.operator_access['\"]",
        re.IGNORECASE,
    ),
]


def _is_raw_guc_manipulation(sql_text: str) -> bool:
    """Return ``True`` if *sql_text* directly manipulates the
    ``app.operator_access`` GUC via ``SET``, ``SET LOCAL``, ``RESET``,
    or ``set_config``.

    Direct GUC manipulation is always forbidden in migration files.  The
    ``operator_access_migration`` context manager is the only permitted
    mechanism.  Any ``execute()`` or ``RunSQL`` call matching this
    detector is a violation regardless of whether it appears inside a
    ``with operator_access_migration(...)`` block.
    """
    if not sql_text:
        return False
    upper = sql_text.strip().upper()
    for pattern in _RAW_GUC_PATTERNS:
        if pattern.search(upper):
            return True
    return False


# =========================================================================
# Detector: assignment+save pattern (obj.organization_id = x; obj.save())
# =========================================================================


def _text_key(node: ast.AST | None) -> str | None:
    """Return a canonical key for *node* for receiver identity matching.

    ``ast.unparse()`` normalises superficial formatting and is resilient to
    context differences (``Store``/``Load``), which is useful when comparing
    the same lexical receiver across assignment and save sites.
    """
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return ast.dump(node, include_attributes=False)


def _extract_org_id_receivers(target: ast.AST) -> list[ast.AST]:
    """Return any ``*.organization_id`` receiver expressions within *target*."""
    receivers: list[ast.AST] = []

    if isinstance(target, ast.Attribute) and target.attr == "organization_id":
        receivers.append(target.value)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            receivers.extend(_extract_org_id_receivers(elt))
    elif isinstance(target, ast.Starred):
        receivers.extend(_extract_org_id_receivers(target.value))

    return receivers


def _save_receiver(call: ast.Call) -> tuple[int, int, str] | None:
    """Return receiver span and key when *call* is ``obj.save()``.

    Returns ``(start_line, end_line, receiver_key)`` when matched.
    """
    if not isinstance(call.func, ast.Attribute):
        return None
    if call.func.attr not in {"save", "asave"}:
        return None
    key = _text_key(call.func.value)
    if key is None:
        return None
    start, end = _node_span(call)
    return start, end, key


def _span_within_ranges(
    start: int,
    end: int,
    ranges: list[tuple[int, int]],
) -> bool:
    """Return True when ``[start, end]`` is fully inside any *ranges* interval."""
    return any(start >= r_start and end <= r_end for r_start, r_end in ranges)


def _check_body_for_assignment_save(
    body: list[ast.stmt],
    func_name: str,
    op_ranges: list[tuple[int, int]],
    violations: list[dict],
) -> None:
    """Scan an immediate function body for assignment/save pair violations.

    The detector now:

    * matches assignment receivers exactly by AST receiver identity,
    * pairs assignments with later saves of that same receiver anywhere in the
      immediate function (no fixed short horizon), and
    * flags violations when either node is outside every
      ``operator_access_migration`` range in that same immediate function.

    It intentionally ignores nested function/class/lambda scopes.
    """
    module_node = ast.Module(body=body, type_ignores=[])

    assignments: list[tuple[int, int, str]] = []
    saves: list[tuple[int, int, str]] = []

    for node in _iter_non_nested_nodes(module_node):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for receiver in _extract_org_id_receivers(target):
                    receiver_key = _text_key(receiver)
                    if receiver_key is not None:
                        start, end = _node_span(node)
                        assignments.append((start, end, receiver_key))
        elif isinstance(node, ast.AnnAssign):
            for receiver in _extract_org_id_receivers(node.target):
                receiver_key = _text_key(receiver)
                if receiver_key is not None:
                    start, end = _node_span(node)
                    assignments.append((start, end, receiver_key))
        elif isinstance(node, ast.NamedExpr):
            for receiver in _extract_org_id_receivers(node.target):
                receiver_key = _text_key(receiver)
                if receiver_key is not None:
                    start, end = _node_span(node)
                    assignments.append((start, end, receiver_key))

        expr: ast.AST | None = None
        if isinstance(node, ast.Expr):
            expr = node.value
        elif isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            expr = node.value

        if expr is None or not isinstance(expr, ast.Call):
            continue
        save = _save_receiver(expr)
        if save is None:
            continue
        saves.append(save)

    if not assignments or not saves:
        return

    for assignment_start, assignment_end, assignment_receiver in assignments:
        assignment_covered = _span_within_ranges(
            assignment_start,
            assignment_end,
            op_ranges,
        )
        violation_save_line: int | None = None

        for save_start, save_end, save_receiver in saves:
            if save_start <= assignment_start:
                continue
            if save_receiver != assignment_receiver:
                continue
            save_covered = _span_within_ranges(save_start, save_end, op_ranges)
            if not (assignment_covered and save_covered):
                violation_save_line = save_start
                break

        if violation_save_line is None:
            continue

        violations.append(
            {
                "func_name": func_name,
                "line": assignment_start,
                "message": (
                    f"organization_id assignment (line {assignment_start}) followed by "
                    f"a same-receiver .save() at line {violation_save_line} that is "
                    f"is not enclosed by `with operator_access_migration("
                    "schema_editor"
                    " ):`. "
                    "ORM writes through the default manager are subject to FORCE "
                    "RLS and need operator_access."
                ),
                "category": "ungated-assignment-save",
            }
        )


def _find_assignment_save_in_function(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    op_ranges_by_function: dict[
        ast.FunctionDef | ast.AsyncFunctionDef, list[tuple[int, int]]
    ],
) -> list[dict]:
    """Detect ``obj.organization_id = value`` followed by ``obj.save()``
    (or ``obj.save(update_fields=...)``) within *func_node* that are NOT
    enclosed by ``operator_access_migration``.

    Recursively checks compound statement bodies (for, while, with, try,
    if).  Returns a list of violation dicts with the line of the assignment.
    """
    violations: list[dict] = []
    op_ranges = op_ranges_by_function.get(func_node, [])
    _check_body_for_assignment_save(
        func_node.body,
        func_node.name,
        op_ranges,
        violations,
    )
    return violations


# =========================================================================
# Detector: wrong editor (operator_access_migration argument != schema_editor)
# =========================================================================


def _extract_bound_names(target: ast.AST) -> list[str]:
    """Return all ``Name`` bindings implied by an assignment target.

    Supports tuples, lists, and starred targets used by Python destructuring.
    """
    names: list[str] = []
    if isinstance(target, ast.Name):
        names.append(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            names.extend(_extract_bound_names(element))
    elif isinstance(target, ast.Starred):
        names.extend(_extract_bound_names(target.value))
    return names


def _iter_function_parameter_names(func_node: ast.AST) -> list[str]:
    """Return all parameter names declared by *func_node*.

    Handles ``ast.FunctionDef``, ``ast.AsyncFunctionDef``, and ``ast.Lambda``.
    """
    if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        return []
    args = func_node.args
    names = [arg.arg for arg in args.posonlyargs + args.args + args.kwonlyargs]
    if args.vararg is not None:
        names.append(args.vararg.arg)
    if args.kwarg is not None:
        names.append(args.kwarg.arg)
    return names


def _iter_function_arg_nodes(func_node: ast.AST) -> list[ast.arg]:
    """Return all ``ast.arg`` nodes declared by *func_node*.

    Handles ``ast.FunctionDef``, ``ast.AsyncFunctionDef``, and ``ast.Lambda``.
    """
    if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        return []
    args = func_node.args
    result: list[ast.arg] = []
    result.extend(args.posonlyargs)
    result.extend(args.args)
    result.extend(args.kwonlyargs)
    if args.vararg is not None:
        result.append(args.vararg)
    if args.kwarg is not None:
        result.append(args.kwarg)
    return result


def _collect_editor_bindings(
    scope_node: ast.AST,
    editor_name: str,
) -> list[tuple[int, str]]:
    """Collect all binding-site lines for *editor_name* in *scope_node*.

    Returns ``(lineno, binding_kind)`` tuples with *binding_kind* describing
    the binding form (``param``, ``assign``, ``annassign``, ``augassign``,
    ``for``, ``with_as``, ``except``, ``import``, ``function``, ``class``,
    ``named_expr``, or ``delete``).

    Nested function/class/lambda scopes are intentionally excluded to enforce
    immediate-scope resolution semantics for editor provenance.
    """
    events: list[tuple[int, str]] = []

    scope_node_lineno = getattr(scope_node, "lineno", 0)

    for arg_name in _iter_function_parameter_names(scope_node):
        if arg_name == editor_name:
            events.append((scope_node_lineno, "param"))

    for node in _iter_non_nested_nodes(scope_node):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            # Names here affect immediate scope only by their own definitions.
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                if node.name == editor_name:
                    events.append(
                        (
                            node.lineno,
                            "class" if isinstance(node, ast.ClassDef) else "function",
                        )
                    )
            continue

        if isinstance(node, (ast.Assign, ast.With)):
            if isinstance(node, ast.With):
                for item in node.items:
                    if item.optional_vars is None:
                        continue
                    if editor_name in _extract_bound_names(item.optional_vars):
                        events.append((node.lineno, "with_as"))
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if editor_name in _extract_bound_names(target):
                        events.append((node.lineno, "assign"))

        if isinstance(node, ast.AnnAssign):
            if editor_name in _extract_bound_names(node.target):
                events.append((node.lineno, "annassign"))

        if isinstance(node, ast.AugAssign):
            if editor_name in _extract_bound_names(node.target):
                events.append((node.lineno, "augassign"))

        if isinstance(node, ast.NamedExpr):
            if editor_name in _extract_bound_names(node.target):
                events.append((node.lineno, "named_expr"))

        if isinstance(node, (ast.For, ast.AsyncFor)):
            if editor_name in _extract_bound_names(node.target):
                events.append((node.lineno, "for"))

        if isinstance(node, ast.ExceptHandler):
            if node.name == editor_name:
                events.append((node.lineno, "except"))

        if isinstance(node, ast.With):
            # Already handled above for 'with-as' bindings.
            pass

        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name
                if bound == editor_name:
                    events.append((node.lineno, "import"))

        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound = alias.asname or alias.name
                if bound == editor_name:
                    events.append((node.lineno, "import"))

        if isinstance(node, ast.Delete):
            for target in node.targets:
                if editor_name in _extract_bound_names(target):
                    events.append((node.lineno, "delete"))

    # Remove duplicates from nodes that can report multiple bindings per line.
    return sorted(set(events), key=lambda item: (item[0], item[1]))


def _binding_kind_for_editor_at_line(
    bindings: list[tuple[int, str]],
    lineno: int,
) -> str | None:
    """Return the binding kind for *editor_name* most recently bound before
    *lineno*.

    ``lineno`` is statement-level; if multiple bindings share the same line,
    the first by kind order in sorted tuples is selected for deterministic output.
    """
    applicable = [(line, kind) for line, kind in bindings if line <= lineno]
    if not applicable:
        return None
    return max(applicable, key=lambda item: item[0])[1]


def _check_wrong_editor(tree: ast.AST) -> list[dict]:
    """Detect ``with operator_access_migration(...)`` blocks where the
    argument passed is not the enclosing function's ``schema_editor``
    parameter.

    Returns a list of violation dicts, one per misused call.
    """
    function_scopes: list[ast.AST] = [
        tree,
        *[
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ],
    ]

    violations: list[dict] = []
    for scope_node in function_scopes:
        scope_name = (
            "<module>"
            if isinstance(scope_node, ast.Module)
            else getattr(scope_node, "name", "<lambda>")
        )
        editor_bindings = _collect_editor_bindings(scope_node, "schema_editor")
        scope_chain = _scope_chain_for_operator_access_call(
            tree, getattr(scope_node, "lineno", 0)
        )

        for node in _iter_non_nested_nodes(scope_node):
            if not isinstance(node, ast.With):
                continue
            for item in node.items:
                if not _is_operator_access_migration_call(
                    item.context_expr,
                    tree=tree,
                    scope_chain=scope_chain,
                    lineno=node.lineno,
                ):
                    continue
                assert isinstance(item.context_expr, ast.Call)
                call = item.context_expr

                if len(call.args) != 1 or call.keywords:
                    violations.append(
                        {
                            "line": node.lineno,
                            "message": (
                                f"operator_access_migration() called at line "
                                f"{node.lineno} must be passed exactly one positional "
                                f"argument: schema_editor.  No keyword args or "
                                f"additional arguments are allowed."
                            ),
                            "category": "wrong-editor",
                        }
                    )
                    continue

                first_arg = call.args[0]
                if not isinstance(first_arg, ast.Name):
                    violations.append(
                        {
                            "line": node.lineno,
                            "message": (
                                f"operator_access_migration() called with an expression "
                                f"at line {node.lineno} that is not a simple name. "
                                "Must use the enclosing callback's own "
                                "'schema_editor' parameter."
                            ),
                            "category": "wrong-editor",
                        }
                    )
                    continue

                if first_arg.id != "schema_editor":
                    violations.append(
                        {
                            "line": node.lineno,
                            "message": (
                                f"operator_access_migration() called with argument "
                                f"'{first_arg.id}' at line {node.lineno}, but only the "
                                "enclosing callback's own 'schema_editor' parameter "
                                "is allowed."
                            ),
                            "category": "wrong-editor",
                        }
                    )
                    continue

                binding_kind = _binding_kind_for_editor_at_line(
                    editor_bindings,
                    node.lineno,
                )
                if binding_kind != "param":
                    if binding_kind is None:
                        message = (
                            f"operator_access_migration() called with argument "
                            f"'schema_editor' at line {node.lineno}, but no enclosing "
                            f"callback parameter named 'schema_editor' is in scope "
                            f"(current scope: '{scope_name}').  Use the callback's "
                            "own parameter."
                        )
                    else:
                        message = (
                            f"operator_access_migration() called with argument "
                            f"'schema_editor' at line {node.lineno}, but that name "
                            f"is currently resolved as a '{binding_kind}' binding in "
                            f"'{scope_name}', not the callback parameter."
                        )
                    violations.append(
                        {
                            "line": node.lineno,
                            "message": message,
                            "category": "wrong-editor",
                        }
                    )

    return violations


# =========================================================================
# Detector: shadowing of operator_access_migration name
# =========================================================================


def _check_operator_access_shadowing(tree: ast.AST) -> list[dict]:
    """Detect shadowing or missing import of ``operator_access_migration``
    using scope-chain-aware binding resolution.

    Uses ``_resolve_active_binding`` with the unified BindingEvent model,
    call-local LEGB resolution, and col_offset ordering:

    * For each call site using a bare ``operator_access_migration`` name,
      resolves the effective binding in the active scope chain.  If the
      effective binding is not ``canonical-import``, the site is flagged.

    * Star imports are handled via the binding-event model: an ``import-star``
      event at module scope only flags the call if no later canonical import
      overrides it (module-final semantics).

    * Module-level late rebindings (e.g. ``for`` target, assignment after
      callback definition) are caught because module-scope resolution uses
      the *last* binding by source order.

    * Non-canonical outer bindings overridden by an inner canonical import
      are NOT flagged (CR-SA88-REV-006 fix).

    * A local name bound after the use site (compile-time local) returns
      ``unbound-local`` and is flagged.
    """
    violations: list[dict] = []

    # Store (call_node, scope_chain) tuples so the unified
    # _consume_canonical predicate can be used for both FQN
    # and bare-name checks.
    operator_access_calls: list[tuple[ast.Call, list[ast.AST], bool]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            chain = _scope_chain_for_operator_access_call(tree, node.lineno)
            for item in node.items:
                if not isinstance(item.context_expr, ast.Call):
                    continue
                context_fn = item.context_expr.func
                if not _is_potential_operator_access_migration_context_expr(context_fn):
                    continue
                is_direct_name = isinstance(context_fn, ast.Name)
                operator_access_calls.append((item.context_expr, chain, is_direct_name))

    # If operator_access_migration is never used as a context manager,
    # shadowing checks are intentionally out-of-scope for this file.
    if not operator_access_calls:
        return violations

    # --- Call-site resolved checks using unified canonical predicate ---
    state_labels: dict[BindingState, str] = {
        BindingState.UNBOUND: "not bound in any reachable scope",
        BindingState.UNKNOWN: "not statically determinable",
        BindingState.DELETED: "deleted",
        BindingState.COUNTERFEIT: "bound through a non-canonical binding",
        BindingState.MIXED: "bound with conflicting states across different paths",
        BindingState.EMPTY: "no binding facts available",
    }

    for call_node, chain, is_direct_name in operator_access_calls:
        call_line = getattr(call_node, "lineno", 0)

        # Use the unified canonical consumption predicate instead of
        # separate _resolve_reaching_state paths.
        is_canonical = _consume_canonical(tree, call_node, scope_chain=chain)

        if not is_canonical:
            # Produce a descriptive violation message.
            reaching = _resolve_reaching_state(
                tree,
                call_line,
                getattr(call_node, "col_offset", 0),
                _OPERATOR_ACCESS_CM_NAME,
            )
            label = state_labels.get(reaching, f"in state '{reaching.value}'")
            violations.append(
                {
                    "filepath": "<unknown>",
                    "line": call_line,
                    "message": (
                        f"operator_access_migration used at line {call_line} is "
                        f"{label}, not the canonical import "
                        f"from quickscale_modules_orgs.tenancy."
                    ),
                    "category": "shadowing",
                }
            )

    return violations


# =========================================================================
# Unified migration checker
# =========================================================================


def check_migration_source(
    source: str,
    filepath: str = "<unknown>",
    module_label: str | None = None,
) -> list[dict]:
    """Check migration source code for cross-table DML without
    ``operator_access_migration``.

    Runs all detectors and returns a combined list of violations.

    Returns a list of violation dicts with keys:
    - ``filepath``: source file path.
    - ``line``: line number of the violating DML.
    - ``message``: human-readable description.

    Args:
        source: The Python source code of the migration file.
        filepath: An optional filepath label for error reporting.
        module_label: Optional Django app label for exemption matching.

    Returns:
        A (possibly empty) list of violation dicts.
    """
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        return [
            {
                "filepath": filepath,
                "line": 0,
                "message": f"Syntax error in migration file: {exc}",
            }
        ]

    op_ranges_by_function = _collect_operator_access_ranges_by_function(tree)

    violations: list[dict] = []

    # --- Detector 1: schema_editor.execute() with cross-table DML ---
    for node in ast.walk(tree):
        if not _is_execute_call(node):
            continue
        assert isinstance(node, ast.Call)

        sql = _extract_sql_arg(node)
        if sql is None:
            # Check for dynamic SQL
            if _is_dynamic_sql_with_org_id(node):
                op_ranges = _operator_access_ranges_for_node(
                    tree,
                    node,
                    op_ranges_by_function,
                )
                if not _node_within_ranges(node, op_ranges):
                    func_name = _find_enclosing_function_name(tree, node.lineno)
                    if not _is_exempt_symbol(
                        filepath,
                        func_name,
                        module_label,
                        category="dynamic-sql",
                    ):
                        violations.append(
                            {
                                "filepath": filepath,
                                "line": node.lineno,
                                "message": (
                                    f"Dynamic SQL at line {node.lineno} contains "
                                    f"organization_id reference and is not "
                                    f"statically analysable — requires manual "
                                    f"review and operator_access_migration() "
                                    f"enclosure."
                                ),
                                "category": "dynamic-sql",
                            }
                        )
            continue

        if not _is_cross_table_dml_assigning_org_id(sql):
            continue

        op_ranges = _operator_access_ranges_for_node(
            tree,
            node,
            op_ranges_by_function,
        )

        if not _node_within_ranges(node, op_ranges):
            func_name = _find_enclosing_function_name(tree, node.lineno)
            if not _is_exempt_symbol(
                filepath,
                func_name,
                module_label,
                category="ungated-raw-sql",
            ):
                violations.append(
                    {
                        "filepath": filepath,
                        "line": node.lineno,
                        "message": (
                            f"Cross-table DML assigning organization_id at "
                            f"line {node.lineno} is not enclosed by "
                            f"`with operator_access_migration"
                            f"(schema_editor):`."
                        ),
                        "category": "ungated-raw-sql",
                    }
                )

    # --- Detector 2: ORM .update(organization_id=...) writes ---
    for node in ast.walk(tree):
        if not _is_orm_update_write(node):
            continue
        assert isinstance(node, ast.Call)

        op_ranges = _operator_access_ranges_for_node(
            tree,
            node,
            op_ranges_by_function,
        )

        if not _node_within_ranges(node, op_ranges):
            func_name = _find_enclosing_function_name(tree, node.lineno)
            if not _is_exempt_symbol(
                filepath,
                func_name,
                module_label,
                category="ungated-orm-write",
            ):
                violations.append(
                    {
                        "filepath": filepath,
                        "line": node.lineno,
                        "message": (
                            f"ORM .update(organization_id=...) at "
                            f"line {node.lineno} is not enclosed by "
                            f"`with operator_access_migration"
                            f"(schema_editor):`.  "
                            f"ORM writes through the default manager are "
                            f"subject to FORCE RLS and need operator_access."
                        ),
                        "category": "ungated-orm-write",
                    }
                )

    # --- Detector 3: migrations.RunSQL with cross-table DML ---
    for node in ast.walk(tree):
        if not _is_runsql_dml_call(node):
            continue
        assert isinstance(node, ast.Call)

        op_ranges = _operator_access_ranges_for_node(
            tree,
            node,
            op_ranges_by_function,
        )

        for sql in _extract_runsql_sql(node):
            if _is_cross_table_dml_assigning_org_id(sql):
                if not _node_within_ranges(node, op_ranges):
                    func_name = _find_enclosing_function_name(tree, node.lineno)
                    if not _is_exempt_symbol(
                        filepath,
                        func_name,
                        module_label,
                        category="ungated-runsql",
                    ):
                        violations.append(
                            {
                                "filepath": filepath,
                                "line": node.lineno,
                                "message": (
                                    f"RunSQL at line {node.lineno} with "
                                    f"cross-table DML assigning "
                                    f"organization_id is not enclosed by "
                                    f"`with operator_access_migration"
                                    f"(schema_editor):`."
                                ),
                                "category": "ungated-runsql",
                            }
                        )

    # --- Detector 4: raw GUC manipulation (non-exemptible) ---
    for node in ast.walk(tree):
        if not _is_execute_call(node):
            continue
        assert isinstance(node, ast.Call)

        sql = _extract_sql_arg(node)
        if sql is None:
            continue
        if _is_raw_guc_manipulation(sql):
            violations.append(
                {
                    "filepath": filepath,
                    "line": node.lineno,
                    "message": (
                        f"Raw GUC manipulation at line {node.lineno}: "
                        f"direct SET/SET LOCAL/RESET/set_config of "
                        f"app.operator_access is forbidden.  Use "
                        f"`with operator_access_migration(schema_editor):` "
                        f"instead."
                    ),
                    "category": "raw-guc",
                }
            )

    # Detector 4b (continues): RunSQL with raw GUC manipulation
    for node in ast.walk(tree):
        if not _is_runsql_dml_call(node):
            continue
        assert isinstance(node, ast.Call)

        for sql in _extract_runsql_sql(node):
            if _is_raw_guc_manipulation(sql):
                violations.append(
                    {
                        "filepath": filepath,
                        "line": node.lineno,
                        "message": (
                            f"RunSQL with raw GUC manipulation at "
                            f"line {node.lineno}: direct SET/SET LOCAL/"
                            f"RESET/set_config of app.operator_access is "
                            f"forbidden.  Use `with "
                            f"operator_access_migration(schema_editor):` "
                            f"instead."
                        ),
                        "category": "raw-guc",
                    }
                )

    # --- Detector 5: assignment+save pattern ---
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            as_violations = _find_assignment_save_in_function(
                node,
                op_ranges_by_function,
            )
            for v in as_violations:
                v["filepath"] = filepath
                # Check exemption
                func_name = v.get("func_name", node.name)
                if not _is_exempt_symbol(
                    filepath,
                    func_name,
                    module_label,
                    category="ungated-assignment-save",
                ):
                    violations.append(v)

    # --- Detector 6: wrong editor ---
    for we_v in _check_wrong_editor(tree):
        we_v.setdefault("filepath", filepath)
        violations.append(we_v)

    # --- Detector 7: shadowing ---
    for sh_v in _check_operator_access_shadowing(tree):
        sh_v.setdefault("filepath", filepath)
        violations.append(sh_v)

    return violations


def _node_span(node: ast.AST) -> tuple[int, int]:
    """Return ``(start_line, end_line)`` for *node*.

    AST callers need both span endpoints to prove same-function coverage: a DML
    call must be fully enclosed by the operator-access wrapper range in the same
    immediate function.
    """
    start = getattr(node, "lineno", None)
    if start is None:
        return (0, 0)
    end = getattr(node, "end_lineno", start)
    return start, end if end is not None else start


def _iter_function_nodes(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Return function nodes in *tree*.

    Works for both synchronous and async migration callbacks.
    """
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _iter_non_nested_nodes(node: ast.AST) -> list[ast.AST]:
    """Iterate descendants without descending into nested function bodies.

    This ensures immediate-function scope checks do not leak wrappers or
    assignment/save checks across nested callback boundaries.
    """
    nodes: list[ast.AST] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            # Preserve the binding site itself (for shadowing/editor checks),
            # but do not recurse into the nested scope.
            nodes.append(child)
            continue
        nodes.append(child)
        nodes.extend(_iter_non_nested_nodes(child))
    return nodes


def _find_enclosing_function_node(
    tree: ast.AST, lineno: int
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return the innermost function containing *lineno*, or ``None``."""
    enclosing: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    best_span: tuple[int, int] | None = None

    for func_node in _iter_function_nodes(tree):
        start = func_node.lineno
        end = func_node.end_lineno or start
        if not (start <= lineno <= end):
            continue
        span = (start, end)
        if best_span is None:
            enclosing = func_node
            best_span = span
            continue
        current_span_size = best_span[1] - best_span[0]
        new_span_size = span[1] - span[0]
        # Pick the smallest enclosing span for true immediate scope.
        if new_span_size < current_span_size:
            enclosing = func_node
            best_span = span

    return enclosing


def _collect_operator_access_ranges_by_function(
    tree: ast.AST,
) -> dict[ast.FunctionDef | ast.AsyncFunctionDef, list[tuple[int, int]]]:
    """Collect ``with operator_access_migration(...)`` ranges per enclosing function.

    Returns a mapping from function nodes to inclusive ``(start_line, end_line)``
    wrapper ranges.
    """
    by_function: dict[
        ast.FunctionDef | ast.AsyncFunctionDef, list[tuple[int, int]]
    ] = {}

    for func_node in _iter_function_nodes(tree):
        ranges: list[tuple[int, int]] = []
        for child in _iter_non_nested_nodes(func_node):
            if not isinstance(child, ast.With):
                continue
            chain = _scope_chain_for_operator_access_call(tree, child.lineno)
            for item in child.items:
                if _is_operator_access_migration_call(
                    item.context_expr,
                    tree=tree,
                    scope_chain=chain,
                    lineno=child.lineno,
                ):
                    ranges.append(_node_span(child))

        # Keep deterministic order for easier proof and stable diagnostics.
        by_function[func_node] = sorted(set(ranges))

    return by_function


def _node_within_ranges(node: ast.AST, ranges: list[tuple[int, int]]) -> bool:
    """Return ``True`` if *node* is fully inside any span in *ranges*."""
    start, end = _node_span(node)
    return any(start >= r_start and end <= r_end for r_start, r_end in ranges)


def _operator_access_ranges_for_node(
    tree: ast.AST,
    node: ast.AST,
    op_ranges_by_function: dict[
        ast.FunctionDef | ast.AsyncFunctionDef, list[tuple[int, int]]
    ],
) -> list[tuple[int, int]]:
    """Return enclosing-function operator-access ranges for *node*.

    This enforces same-function scope: an inner function must supply its own
    `with operator_access_migration(...)` wrapper to satisfy checks for
    operations inside that immediate lexical function.
    """
    lineno = getattr(node, "lineno", -1)
    enclosing_func = _find_enclosing_function_node(tree, lineno)
    if enclosing_func is None:
        return []
    return op_ranges_by_function.get(enclosing_func, [])


def _find_enclosing_function_name(tree: ast.AST, lineno: int) -> str | None:
    """Return the name of the function that contains *lineno*.

    Returns ``None`` if the line is not inside any function definition.
    """
    enclosing = _find_enclosing_function_node(tree, lineno)
    if enclosing is None:
        return None
    return enclosing.name


def get_migration_files() -> list[Path]:
    """Backward-compatible alias for the full manifested migration file scan."""
    return get_all_migration_files()


def get_all_module_migration_dirs(
    modules_root: Path | str | None = None,
) -> list[Path]:
    """Return sorted list of migration directory paths for ALL manifested
    ``quickscale_modules_*`` packages found on the filesystem, independent
    of Django ``INSTALLED_APPS``.

    Discovers ``src/quickscale_modules_*/migrations/`` directories within
    the ``quickscale_modules`` workspace, checking both ``src/`` layout and
    flat package layout.

    Each returned path is verified to exist and be a directory.  Unreadable
    or inaccessible directories are reported via ``pytest.fail``.
    """
    import pytest

    # Determine the quickscale_modules workspace root.
    # Default is three levels up from this test file.
    if modules_root is None:
        this_file = Path(__file__).resolve()
        qs_modules_root = this_file.parents[2]
    else:
        qs_modules_root = Path(modules_root)

    if not qs_modules_root.is_dir():
        pytest.fail(
            f"Cannot discover quickscale_modules workspace: "
            f"{qs_modules_root} is not a directory"
        )

    try:
        entries = sorted(qs_modules_root.iterdir(), key=lambda p: p.name)
    except OSError as exc:
        pytest.fail(f"Failed to list module workspace {qs_modules_root}: {exc}")

    dirs: set[Path] = set()

    for entry in entries:
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if not (entry / "module.yml").is_file():
            continue

        module_pkg_name = f"quickscale_modules_{entry.name.replace('-', '_')}"

        # Check for src/quickscale_modules_<module>/migrations/ layout
        src_pkg = entry / "src" / module_pkg_name
        if src_pkg.is_dir():
            migration_dir = src_pkg / "migrations"
            if migration_dir.is_dir():
                dirs.add(migration_dir.resolve())

        # Also check flat layout: quickscale_modules_<name>/migrations/
        pkg_dir = entry / module_pkg_name
        if pkg_dir.is_dir():
            migration_dir = pkg_dir / "migrations"
            if migration_dir.is_dir():
                dirs.add(migration_dir.resolve())

    if not dirs:
        pytest.fail(
            f"No quickscale_modules migration directories found under {qs_modules_root}"
        )

    return sorted(dirs, key=lambda p: str(p))


def get_all_migration_files(
    modules_root: Path | str | None = None,
) -> list[Path]:
    """Return all migration files for manifested modules in stable order.

    Includes only Python files that look like timestamp-numbered migration files.
    """
    migration_files: set[Path] = set()
    for directory in get_all_module_migration_dirs(modules_root):
        try:
            candidates = sorted(directory.glob("[0-9]*.py"), key=lambda p: p.name)
        except OSError as exc:
            pytest.fail(f"Failed to list migration files in {directory}: {exc}")

        for migration_file in candidates:
            if migration_file.is_file():
                migration_files.add(migration_file.resolve())

    if not migration_files:
        pytest.fail(
            "No migration files discovered for manifested quickscale_modules "
            f"under modules_root={modules_root or '<default>'}"
        )

    return sorted(migration_files, key=lambda p: str(p))


def _read_migration_source_with_read_error(
    filepath: Path,
) -> tuple[str | None, list[dict]]:
    """Read migration source text and emit migration-read-error violations.

    Returns ``(source, violations)`` where *violations* contains an explicit
    ``migration-read-error`` entry when ``read_text()`` fails.
    """
    try:
        return filepath.read_text(encoding="utf-8"), []
    except OSError as exc:
        return None, [
            {
                "filepath": str(filepath),
                "line": 0,
                "message": f"migration-read-error: cannot read migration file: {exc}",
                "category": "migration-read-error",
            }
        ]


# =========================================================================
# SA88a.1 Phase 1 — Observation and flow-analysis helpers
# =========================================================================


def _observe_name_fact(
    tree: ast.AST,
    lineno: int,
    col_offset: int,
    name: str,
    scope_chain: list[ast.AST] | None = None,
) -> BindingFact:
    """Observe the binding state of *name* at the exact AST position
    ``(lineno, col_offset)``.

    Uses the existing ``_resolve_active_binding`` scope-chain-aware
    resolver and maps the active ``BindingEvent`` (or ``None``) to a
    ``BindingFact``.
    """
    reaching = _resolve_reaching_state(tree, lineno, col_offset, name, scope_chain)
    # Map reaching state to BindingFact.  Use (lineno, col_offset) for the
    # fact location; for BOUND we need the source_module.
    source: str | None = None
    if reaching == BindingState.BOUND:
        loc_active = _resolve_owner_aware_binding(
            tree, lineno, col_offset, name, scope_chain
        )
        if loc_active is not None and loc_active.source_module is not None:
            source = loc_active.source_module
    return BindingFact(
        name=name,
        state=reaching,
        lineno=lineno,
        col_offset=col_offset,
        source_module=source,
    )


def _observe_call_fact(
    tree: ast.AST,
    call_node: ast.Call,
    scope_chain: list[ast.AST] | None = None,
) -> BindingFact:
    """Observe the binding state of the callable at *call_node*'s
    exact AST evaluation point.

    For bare-name calls (``operator_access_migration(...)``), resolves
    the name directly.  For FQN calls
    (``quickscale_modules_orgs.tenancy.operator_access_migration(...)``),
    resolves the root module name.  All other call forms return
    ``COUNTERFEIT`` or ``UNKNOWN``.
    """
    lineno = getattr(call_node, "lineno", 0)
    col_offset = getattr(call_node, "col_offset", 0)
    func = call_node.func

    # --- Bare-name call ---
    if isinstance(func, ast.Name) and func.id == _OPERATOR_ACCESS_CM_NAME:
        return _observe_name_fact(
            tree, lineno, col_offset, _OPERATOR_ACCESS_CM_NAME, scope_chain
        )

    # --- FQN or attribute call ---
    if isinstance(func, ast.Attribute) and func.attr == _OPERATOR_ACCESS_CM_NAME:
        resolved_fqn = _resolve_attribute_fqn(func)
        if resolved_fqn == _CANONICAL_OPERATOR_ACCESS_FQN:
            # Resolve the root module name.
            return _observe_name_fact(
                tree, lineno, col_offset, "quickscale_modules_orgs", scope_chain
            )
        # Non-canonical FQN (e.g. tenancy.operator_access_migration)
        return BindingFact(
            name=_OPERATOR_ACCESS_CM_NAME,
            state=BindingState.COUNTERFEIT,
            lineno=lineno,
            col_offset=col_offset,
        )

    # --- Unknown call expression ---
    return BindingFact(
        name=_OPERATOR_ACCESS_CM_NAME,
        state=BindingState.UNKNOWN,
        lineno=lineno,
        col_offset=col_offset,
    )


# --- Flow analysis helpers ---


def _stmt_is_abrupt_exit(node: ast.AST) -> bool:
    """Return ``True`` if *node* terminates its block with an abrupt exit
    (return, raise, break, or continue) at the statement level.

    Does NOT descend into nested function/class/lambda scopes.
    """
    return isinstance(node, (ast.Return, ast.Raise, ast.Break, ast.Continue))


def _block_has_live_path_to(
    body: list[ast.AST],
    target_lineno: int,
) -> bool:
    """Check whether execution can reach *target_lineno* through *body*.

    Walks the statement list without descending into nested
    function/class/lambda scopes.  Returns ``True`` if at least one
    control-flow path reaches *target_lineno* without hitting an
    unconditional abrupt exit.

    ``False`` means every path terminates before *target_lineno* — the
    code at that line is dead/unreachable.
    """
    for stmt in body:
        stmt_lineno = getattr(stmt, "lineno", 0)
        if stmt_lineno >= target_lineno:
            return True

        # Skip nested function/class/lambda — their internal flow does
        # not affect the outer scope's predecessor state.
        if isinstance(
            stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue

        # Unconditional abrupt exit at this level terminates the path.
        if _stmt_is_abrupt_exit(stmt):
            return False

        # --- if / elif / else ---
        if isinstance(stmt, ast.If):
            if_body_live = _block_has_live_path_to(stmt.body, target_lineno)
            else_live = (
                _block_has_live_path_to(stmt.orelse, target_lineno)
                if stmt.orelse
                else True
            )
            if if_body_live or else_live:
                return True
            return False

        # --- try / except / else / finally ---
        if isinstance(stmt, ast.Try):
            try_live = _block_has_live_path_to(stmt.body, target_lineno)
            handlers_live = any(
                _block_has_live_path_to(handler.body, target_lineno)
                for handler in stmt.handlers
            )
            else_live = (
                _block_has_live_path_to(stmt.orelse, target_lineno)
                if stmt.orelse
                else False
            )
            if try_live or handlers_live or else_live:
                return True
            # finally always runs; if the target is after the try block
            # and the finally body doesn't terminate, there's a live path.
            if stmt.finalbody:
                finally_live = _block_has_live_path_to(stmt.finalbody, target_lineno)
                if finally_live:
                    return True
            return False

        # --- with ---
        if isinstance(stmt, ast.With):
            if not _block_has_live_path_to(stmt.body, target_lineno):
                return False
            continue

        # --- for / while (loops) ---
        # Loops may execute zero times, so there is always a live
        # predecessor path through the loop (the skip-case).
        if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            # Check whether body statements reach the target.
            loop_body_live = _block_has_live_path_to(stmt.body, target_lineno)
            if not loop_body_live and not getattr(stmt, "orelse", None):
                # All body paths terminate, but the loop might not execute.
                # If the target is after the loop, there is a live path.
                if any(getattr(s, "lineno", 0) >= target_lineno for s in stmt.body):
                    continue
            continue

        # Other statements (assignments, expressions, etc.) — continue.

    return True


def _isolate_nested_scope_facts(
    facts: tuple[BindingFact, ...],
    scope_node: ast.AST,
) -> tuple[BindingFact, ...]:
    """Filter *facts* to those belonging to *scope_node* (non-nested).

    Removes any ``BindingFact`` originating from inside a nested
    function/class/lambda body within *scope_node*.
    """
    if not isinstance(
        scope_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module, ast.Lambda)
    ):
        return facts

    # Collect nested function/class boundaries.
    nested_boundaries: list[tuple[int, int]] = []
    for node in ast.walk(scope_node):
        if node is scope_node:
            continue
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            n_start = getattr(node, "lineno", 0)
            n_end = getattr(node, "end_lineno", n_start)
            nested_boundaries.append((n_start, n_end))

    result: list[BindingFact] = []
    for fact in facts:
        fact_lineno = fact.lineno
        in_nested = any(
            n_start <= fact_lineno <= n_end for n_start, n_end in nested_boundaries
        )
        if not in_nested:
            result.append(fact)
    return tuple(result)


def _consume_canonical(
    tree: ast.AST,
    call_node: ast.Call,
    scope_chain: list[ast.AST] | None = None,
    predecessor_body: list[ast.AST] | None = None,
) -> bool:
    """Centralized predicate: return ``True`` if *call_node* is a canonical
    consumption of the ``operator_access_migration`` name.

    A canonical consumption requires:
    1. The callable resolves to a ``BOUND`` canonical binding at the
       exact AST evaluation point (via :func:`_observe_call_fact`).
    2. There is at least one live predecessor path to the call site
       (when *predecessor_body* is provided).

    This is the universal predicate that Phase 2 and Phase 3 will build
    on.  Phase 1 provides the centralized implementation for direct
    test consumption.
    """
    fact = _observe_call_fact(tree, call_node, scope_chain)
    if not fact.is_canonical():
        return False
    # Only require live predecessor when body is provided.
    if predecessor_body is not None:
        call_lineno = getattr(call_node, "lineno", 0)
        if not _block_has_live_path_to(predecessor_body, call_lineno):
            return False
    return True


# =========================================================================
# Synthetic proof tests
# =========================================================================

_SQL_WITH_SUBQUERY = (
    "UPDATE some_table "
    "SET organization_id = (SELECT id FROM other_table "
    "WHERE other_table.id = some_table.other_id) "
    "WHERE organization_id IS NULL"
)

UNGATED_CODE = f"""
def forward(apps, schema_editor):
    schema_editor.execute(
        {_SQL_WITH_SUBQUERY!r}
    )
"""

WRAPPED_CODE = f"""
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            {_SQL_WITH_SUBQUERY!r}
        )
"""

DDL_CODE = '''
def forward(apps, schema_editor):
    """DDL-only migration — no cross-table DML."""
    schema_editor.execute(
        "ALTER TABLE some_table ENABLE ROW LEVEL SECURITY"
    )
'''

SELF_UPDATE_CODE = '''
def forward(apps, schema_editor):
    """Self-table only — no cross-table subquery."""
    schema_editor.execute(
        "UPDATE some_table SET organization_id = \'a1b2c3d4\' WHERE id = 1"
    )
'''

READ_ONLY_CODE = '''
def forward(apps, schema_editor):
    """Read-only SELECT — not DML."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM some_table WHERE organization_id IS NULL"
        )
'''

NO_EXECUTE_CODE = '''
def forward(apps, schema_editor):
    """ORM-only backfill — no raw execute() calls."""
    from django.apps import apps as dj_apps
    MyModel = dj_apps.get_model("some_app", "MyModel")
    for obj in MyModel._base_manager.filter(organization__isnull=True):
        obj.organization_id = some_org_id
        obj.save()
'''

UNGATED_ORM_UPDATE_CODE = """
def forward(apps, schema_editor):
    MyModel._base_manager.filter(fk_id=1).update(
        organization_id=some_org_id,
    )
"""

WRAPPED_ORM_UPDATE_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        MyModel._base_manager.filter(fk_id=1).update(
            organization_id=some_org_id,
        )
"""

UNGATED_RUNSQL_CODE = """
def forward(apps, schema_editor):
    migrations.RunSQL(
        "UPDATE t SET organization_id = (SELECT id FROM other WHERE other.x = t.x)"
    )
"""

WRAPPED_RUNSQL_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        migrations.RunSQL(
            "UPDATE t SET organization_id = (SELECT id FROM other WHERE other.x = t.x)"
        )
"""

DYNAMIC_SQL_CODE = """
def forward(apps, schema_editor):
    table = "my_table"
    schema_editor.execute(
        f"UPDATE {table} SET organization_id = (SELECT id FROM other WHERE id = 1)"
    )
"""

EXEMPT_CRM_CODE = '''
def _backfill_contactnote_org(apps, schema_editor):
    """ORM _base_manager backfill — exempt (SA84)."""
    del schema_editor
    ContactNote = apps.get_model("quickscale_modules_crm", "ContactNote")
    Contact = apps.get_model("quickscale_modules_crm", "Contact")
    for note in ContactNote._base_manager.filter(organization__isnull=True):
        parent = Contact._base_manager.get(pk=note.contact_id)
        ContactNote._base_manager.filter(pk=note.pk).update(
            organization_id=parent.organization_id
        )

def forward(apps, schema_editor):
    _backfill_contactnote_org(apps, schema_editor)
'''

# Cross-table UPDATE ... FROM (no parenthesised subquery)
UPDATE_FROM_SQL = (
    "UPDATE t "
    "SET organization_id = s.organization_id "
    "FROM source_table s "
    "WHERE t.id = s.t_id"
)

UNGATED_UPDATE_FROM_CODE = f"""
def forward(apps, schema_editor):
    schema_editor.execute(
        {UPDATE_FROM_SQL!r}
    )
"""

WRAPPED_UPDATE_FROM_CODE = f"""
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            {UPDATE_FROM_SQL!r}
        )
"""

# INSERT INTO ... SELECT (no parenthesised subquery)
INSERT_SELECT_SQL = (
    "INSERT INTO target_table (organization_id, name) "
    "SELECT s.organization_id, s.name "
    "FROM source_table s "
    "WHERE s.id = 1"
)

UNGATED_INSERT_SELECT_CODE = f"""
def forward(apps, schema_editor):
    schema_editor.execute(
        {INSERT_SELECT_SQL!r}
    )
"""

WRAPPED_INSERT_SELECT_CODE = f"""
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            {INSERT_SELECT_SQL!r}
        )
"""

# CRM exempt function with ADDITIONAL raw SQL (to prove category-specific exemption)
EXEMPT_CRM_WITH_RAW_SQL_CODE = '''
def _backfill_contactnote_org(apps, schema_editor):
    """ORM _base_manager backfill — exempt (SA84) for ORM-update only."""
    del schema_editor
    ContactNote = apps.get_model("quickscale_modules_crm", "ContactNote")
    Contact = apps.get_model("quickscale_modules_crm", "Contact")
    for note in ContactNote._base_manager.filter(organization__isnull=True):
        parent = Contact._base_manager.get(pk=note.contact_id)
        ContactNote._base_manager.filter(pk=note.pk).update(
            organization_id=parent.organization_id
        )
    # RAW SQL execute in the SAME exempt function — should still be detected
    # because the exemption is category-specific (ungated-orm-write only).
    schema_editor.execute(
        "UPDATE some_table SET organization_id = "
        "(SELECT id FROM other_table WHERE id = 1) "
    )

def forward(apps, schema_editor):
    _backfill_contactnote_org(apps, schema_editor)
'''


# =========================================================================
# Raw GUC manipulation synthetic test code
# =========================================================================

_RAW_SET_LOCAL_SQL = "SET LOCAL app.operator_access = 'on'"

RAW_GUC_SET_LOCAL_CODE = f"""
def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute({_RAW_SET_LOCAL_SQL!r})
"""

RAW_GUC_SET_CODE = """
def forward(apps, schema_editor):
    schema_editor.execute("SET app.operator_access = 'on'")
"""

RAW_GUC_RESET_CODE = """
def forward(apps, schema_editor):
    schema_editor.execute("RESET app.operator_access")
"""

RAW_GUC_SET_CONFIG_CODE = """
def forward(apps, schema_editor):
    schema_editor.execute(
        "SELECT set_config('app.operator_access', 'on', true)"
    )
"""

RAW_GUC_RUNSQL_CODE = """
def forward(apps, schema_editor):
    migrations.RunSQL("SET LOCAL app.operator_access = 'on'")
"""

RAW_GUC_CLEAN_CODE = """
def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# =========================================================================
# Wrong editor synthetic test code
# =========================================================================

WRONG_EDITOR_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    wrong_editor = schema_editor
    with operator_access_migration(wrong_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

WRONG_EDITOR_KEYWORD_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(editor=schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

WRONG_EDITOR_EXTRA_ARGS_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor, schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

WRONG_EDITOR_NO_ARGS_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration():
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

WRONG_EDITOR_NON_NAME_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor.connection):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

WRONG_EDITOR_REBOUND_ASSIGN_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    schema_editor = schema_editor.connection
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

WRONG_EDITOR_REBOUND_TUPLE_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    (schema_editor,) = [schema_editor.connection]
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

WRONG_EDITOR_REBOUND_LIST_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    [schema_editor] = [schema_editor.connection]
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

WRONG_EDITOR_REBOUND_STARRED_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    *schema_editor, = [schema_editor.connection]
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

WRONG_EDITOR_REBOUND_WITH_AS_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with open("/tmp/example.txt") as schema_editor:
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )
"""

WRONG_EDITOR_REBOUND_FOR_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    for schema_editor in []:
        pass
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

WRONG_EDITOR_REBOUND_EXCEPT_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    try:
        raise ValueError
    except Exception as schema_editor:
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )
"""

WRONG_EDITOR_REBOUND_IMPORT_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    import builtins as schema_editor
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

WRONG_EDITOR_REBOUND_FUNCTION_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    def schema_editor(_):
        return None

    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

WRONG_EDITOR_REBOUND_CLASS_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    class schema_editor:
        pass

    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

CANONICAL_MISSING_IMPORT_CODE = """
def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# =========================================================================
# Shadowing synthetic test code
# =========================================================================

SHADOWING_ASSIGN_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    operator_access_migration = lambda x: x  # shadowing
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

SHADOWING_IMPORT_CODE = """
from somewhere import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

SHADOWING_ALIAS_CODE = """
from quickscale_modules_orgs.tenancy import something as operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

CANONICAL_FQN_CODE = """
import quickscale_modules_orgs

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

IMPORT_STAR_CODE = """
from quickscale_modules_orgs.tenancy import *

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

ALIAS_MODULE_CODE = """
import quickscale_modules_orgs.tenancy as tenancy

def forward(apps, schema_editor):
    with tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# =========================================================================
# Additional shadowing synthetic test code (CR-SA88-REV-006)
# =========================================================================

SHADOWING_FUNCTION_DEF_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    def operator_access_migration(x):
        return x
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

SHADOWING_CLASS_DEF_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    class operator_access_migration:
        pass
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

SHADOWING_ANNASSIGN_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    operator_access_migration: str = "not-the-real-one"
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

SHADOWING_WALRUS_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    if (operator_access_migration := lambda x: x):
        pass
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

SHADOWING_PARAMETER_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor, operator_access_migration=None):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# =========================================================================
# CR-SA88-REV-006: exhaustive evasion/legitimate-binding test constants
# =========================================================================

COUNTERFEIT_ROOT_FQN_CODE = """
from evil_package import quickscale_modules_orgs

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Counterfeit root: ``from evil import quickscale_modules_orgs`` then
FQN call.  The dotted string matches the canonical FQN but the root
name is bound to a different package."""

LATE_MODULE_FOR_REBIND_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )

for operator_access_migration in [lambda x: None]:
    pass
"""
"""Late module-level ``for``-target rebinding after callback definition.
When Django invokes the callback, the global binding is the loop variable,
not the canonical import."""

LATE_MODULE_ASSIGN_REBIND_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )

operator_access_migration = lambda x: None
"""
"""Late module-level assignment rebinding after callback definition."""

LATE_MODULE_ANNASSIGN_REBIND_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )

operator_access_migration: object = lambda x: None
"""
"""Late module-level annotated assignment rebinding."""

LATE_MODULE_WALRUS_REBIND_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )

if (operator_access_migration := lambda x: None):
    pass
"""
"""Late module-level walrus-operator rebinding after callback definition."""

LATE_MODULE_AUGASSIGN_REBIND_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )

operator_access_migration += "suffix"
"""
"""Late module-level augmented assignment rebinding after callback
definition.  (Augmented assignment references the prior value so this
would raise at runtime, but for the analyzer it is a binding event.)"""

LATE_MODULE_FUNCTION_DEF_REBIND_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )

def operator_access_migration(x):
    return x
"""
"""Late module-level function definition that replaces the canonical
import after callback definition."""

LATE_MODULE_CLASS_DEF_REBIND_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )

class operator_access_migration:
    pass
"""
"""Late module-level class definition that replaces the canonical
import after callback definition."""

INNER_CANONICAL_OVERRIDE_CODE = """
operator_access_migration = lambda x: None

def forward(apps, schema_editor):
    from quickscale_modules_orgs.tenancy import operator_access_migration
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Positive test: a module-level counterfeit is overridden by an inner
canonical import.  The scope-aware resolver should NOT flag this as a
shadowing violation because the effective binding at the call site is
the canonical import."""

INNER_CANONICAL_OVERRIDE_NESTED_CODE = """
operator_access_migration = lambda x: None

def forward(apps, schema_editor):
    def inner():
        from quickscale_modules_orgs.tenancy import operator_access_migration
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )
    inner()
"""
"""Positive test: inner-function canonical import overrides module-level
counterfeit in a nested scope chain."""

CANONICAL_ASSIGN_ALIAS_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    op_acc_mig = operator_access_migration
    with op_acc_mig(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Positive test: creating an alias name (not shadowing the canonical
name) does not produce a shadowing violation.  The ``with`` call uses
the alias which is a non-canonical call (separate detection), but the
canonical name itself is never rebound."""

PARAM_SHADOWING_POSONLY_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor, operator_access_migration=None, /):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Positional-only parameter shadows the canonical name (Python 3.8+ ``/``)."""

PARAM_SHADOWING_KWONLY_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor, *, operator_access_migration=None):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Keyword-only parameter shadows the canonical name (``*`` separator)."""

PARAM_SHADOWING_VARARG_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor, *operator_access_migration):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Variable-length positional parameter (``*args``) shadows the canonical
name."""

PARAM_SHADOWING_KWARG_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor, **operator_access_migration):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Variable-length keyword parameter (``**kwargs``) shadows the canonical
name."""

FUNCTION_SCOPE_REBIND_NOT_GLOBAL_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    def operator_access_migration(x):
        return x
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )

def other_func(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Positive test: a function-scope rebind in ``forward`` only shadows
the canonical name in that function.  ``other_func`` still sees the
module-level canonical import."""

FQN_WITH_IMPORT_MODULE_ALIAS_CODE = """
import quickscale_modules_orgs.tenancy as tenancy

def forward(apps, schema_editor):
    with tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Module alias using ``import ... as`` is not the canonical FQN and is
a non-canonical call.  The shadowing checker should produce a violation
because the call is not recognized as canonical."""

# =========================================================================
# CR-SA88-REV-006: exhaustive counterfeit-root forms (scope-chain-aware)
# =========================================================================

COUNTERFEIT_ROOT_ASSIGN_CODE = """
quickscale_modules_orgs = "fake"

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Counterfeit root via assignment: ``quickscale_modules_orgs = 'fake'`` then
FQN call.  The dotted string matches the canonical FQN but the root name is
bound via assignment, not a real import."""

COUNTERFEIT_ROOT_FUNCTION_CODE = """
def quickscale_modules_orgs():
    return None

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Counterfeit root via function definition: the root name is bound as a
local function, not the real module."""

COUNTERFEIT_ROOT_CLASS_CODE = """
class quickscale_modules_orgs:
    pass

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Counterfeit root via class definition: the root name is bound as a local
class, not the real module."""

COUNTERFEIT_ROOT_FOR_CODE = """
for quickscale_modules_orgs in [None]:
    pass

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Counterfeit root via for-loop target: the root name is bound as a loop
variable, not the real module."""

COUNTERFEIT_ROOT_WITHAS_CODE = """
from contextlib import nullcontext

with nullcontext() as quickscale_modules_orgs:
    pass

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Counterfeit root via with-as target: the root name is bound as a
context manager target, not the real module."""

COUNTERFEIT_ROOT_EXCEPT_CODE = """
try:
    raise ValueError
except ValueError as quickscale_modules_orgs:
    pass

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Counterfeit root via except handler: the root name is bound as an
exception target, not the real module."""

COUNTERFEIT_ROOT_PARAM_CODE = """
def forward(quickscale_modules_orgs, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Counterfeit root via function parameter: the root name is bound as a
parameter of the callback, not the real module."""

COUNTERFEIT_ROOT_IMPORT_ALIAS_CODE = """
import sys as quickscale_modules_orgs

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Counterfeit root via import alias: ``import sys as quickscale_modules_orgs``
binds the name to the sys module, not the real quickscale_modules_orgs."""

COUNTERFEIT_THEN_CANONICAL_ROOT_CODE = """
from evil_package import quickscale_modules_orgs
import quickscale_modules_orgs.tenancy

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Positive test: a counterfeit root binding followed by a later canonical
``import quickscale_modules_orgs.tenancy``.  Module-final semantics should
use the later canonical import as the active root binding."""

COUNTERFEIT_THEN_CANONICAL_ROOT_VIA_IMPORT_CODE = """
from evil_package import quickscale_modules_orgs
import quickscale_modules_orgs

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Positive test: a counterfeit root followed by ``import quickscale_modules_orgs``
at module level.  The later exact import should restore canonical root binding."""

LATER_COUNTERFEIT_ROOT_AFTER_CANONICAL_CODE = """
import quickscale_modules_orgs.tenancy
quickscale_modules_orgs = "fake"

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""A later assignment rebinding after the canonical import makes the root
counterfeit at module-final state."""

STAR_IMPORT_THEN_CANONICAL_CODE = """
from quickscale_modules_orgs.tenancy import *
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
"""Positive test: a star import at module level (uncertain provenance) is
overridden by a later exact canonical import.  Module-final semantics should
produce zero shadowing violations."""

STAR_IMPORT_THEN_LATE_COUNTERFEIT_CODE = """
from quickscale_modules_orgs.tenancy import *
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )

operator_access_migration = lambda x: None
"""
"""Negative test: star import then canonical import then late module-level
counterfeit.  The last binding is counterfeit, so the call should be flagged."""

USE_BEFORE_FUNCTION_LOCAL_BIND_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
    operator_access_migration = lambda x: None
"""
"""Function-scope compile-time-local rule: ``operator_access_migration`` is
assigned later in the function, making it LOCAL at compile time.  The
``with`` call site must NOT fall through to the module-level canonical
import.  Instead it should be resolved as an unbound-local and flagged."""

# =========================================================================
# Assignment+save synthetic test code
# =========================================================================

ASSIGN_SAVE_UNGATED_CODE = """
def forward(apps, schema_editor):
    MyModel = apps.get_model("some_app", "MyModel")
    for obj in MyModel.objects.all():
        obj.organization_id = "some-org-id"
        obj.save()
"""

ASSIGN_SAVE_WRAPPED_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    MyModel = apps.get_model("some_app", "MyModel")
    with operator_access_migration(schema_editor):
        for obj in MyModel.objects.all():
            obj.organization_id = "some-org-id"
            obj.save()
"""

ASSIGN_SAVE_UPDATE_FIELDS_CODE = """
def forward(apps, schema_editor):
    MyModel = apps.get_model("some_app", "MyModel")
    for obj in MyModel.objects.filter(organization__isnull=True):
        obj.organization_id = "some-org-id"
        obj.save(update_fields=["organization_id"])
"""

ASSIGN_SAVE_BASE_MANAGER_CODE = """
def forward(apps, schema_editor):
    MyModel = apps.get_model("some_app", "MyModel")
    for obj in MyModel._base_manager.filter(active=True):
        obj.organization_id = "some-org-id"
        obj.save()
"""

ASSIGN_SAVE_OUTER_WRAPPED_INNER_UNGATED_CODE = """
def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):

        def _inner():
            MyModel = apps.get_model("some_app", "MyModel")
            for obj in MyModel.objects.filter(organization__isnull=True):
                obj.organization_id = "some-org-id"
                obj.save()

        _inner()
"""

ASSIGN_SAVE_OUTER_WRAPPED_INNER_WRAPPED_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):

        def _inner(schema_editor):
            MyModel = apps.get_model("some_app", "MyModel")
            with operator_access_migration(schema_editor):
                for obj in MyModel.objects.filter(organization__isnull=True):
                    obj.organization_id = "some-org-id"
                    obj.save()

        _inner(schema_editor)
"""

ASSIGN_SAVE_FAR_APART_CODE = """
def forward(apps, schema_editor):
    MyModel = apps.get_model("some_app", "MyModel")
    for obj in MyModel.objects.filter(organization__isnull=True):
        obj.organization_id = "some-org-id"
        obj.name = "name-1"
        obj.status = "active"
        obj.save(update_fields=["name"])
        obj.update_timestamp = "now"
        obj.save()
"""

ASSIGN_SAVE_ANNASSIGN_CODE = """
def forward(apps, schema_editor):
    MyModel = apps.get_model("some_app", "MyModel")
    for obj in MyModel.objects.filter(organization__isnull=True):
        obj.organization_id: str = "some-org-id"
        obj.save()
"""

ASSIGN_SAVE_DIFFERENT_RECEIVER_CODE = """
def forward(apps, schema_editor):
    MyModel = apps.get_model("some_app", "MyModel")
    src = MyModel.objects.filter(organization__isnull=True)[0]
    dst = MyModel.objects.filter(organization__isnull=False)[0]
    src.organization_id = "src-org-id"
    dst.save()
"""

# =========================================================================
# Canonical import test code
# =========================================================================

CANONICAL_IMPORT_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

NESTED_INNER_FUNCTION_UNGATED_CODE = """
def forward(apps, schema_editor):

    def _inner():
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
            " WHERE t.x = 1"
        )

    _inner()
"""

NESTED_INNER_FUNCTION_WRAPPED_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):

    def _inner(schema_editor):
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
                " WHERE t.x = 1"
            )

    _inner(schema_editor)
"""

NESTED_WRONG_EDITOR_CAPTURE_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):

    def _inner():
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
                " WHERE t.x = 1"
            )

    _inner()
"""


# =========================================================================
# SA88a.1 Phase 1 — Synthetic test code
# =========================================================================

# T1: wrapper call inside a counterfeit-root branch
T1_COUNTERFEIT_BRANCH_CODE = """
from evil_package import quickscale_modules_orgs

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# T2: both branches terminate (return/raise) before post-join wrapper
T2_BOTH_BRANCHES_TERMINATE_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    if some_condition:
        return
    else:
        raise ValueError()
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# T3: unbound owner — root module name never imported
T3_UNBOUND_OWNER_CODE = """
def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# C1: canonical bare-name import
C1_CANONICAL_BARE_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# C2: canonical FQN call
C2_CANONICAL_FQN_CODE = """
import quickscale_modules_orgs

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# C9: counterfeit branch returns before post-join canonical wrapper
C9_COUNTERFEIT_RETURNS_BRANCH_CODE = """
from evil_package import quickscale_modules_orgs
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    if some_condition:
        with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )
        return
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# C10: counterfeit branch raises before post-join canonical wrapper
C10_COUNTERFEIT_RAISES_BRANCH_CODE = """
from evil_package import quickscale_modules_orgs
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    if some_condition:
        with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )
        raise RuntimeError()
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# C11: nested return does not terminate outer canonical path
C11_NESTED_RETURN_ISOLATED_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    def inner():
        return "something"
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""


class TestSA88aPhase1BindingFlow:
    """Phase 1 binding-flow and evaluation-order primitives for SA88a.1.

    These tests exercise the abstract-domain state primitives
    (``BindingState``, ``BindingFact``, ``FlowResult``) and flow analysis
    (predecessor tracking, nested-scope isolation, evaluation-order
    transfer) on direct synthetic code.  They do NOT go through the full
    ``check_migration_source`` gate — they test the Phase 1 primitives
    directly.

    Tests are labeled T1–T3 (new negative proofs) and C1/C2/C9–C11
    (controls demonstrating positive and negative canonical consumption).
    """

    # =========================================================
    # T1: wrapper inside counterfeit branch
    # =========================================================

    def test_t1_counterfeit_root_fqn_call_observed(self) -> None:
        """T1: An FQN call using a counterfeit root binding is observed
        at the exact AST evaluation point as COUNTERFEIT, not BOUND."""
        tree = ast.parse(T1_COUNTERFEIT_BRANCH_CODE)
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                call = node.items[0].context_expr
                fact = _observe_call_fact(tree, call)
                assert not fact.is_canonical(), (
                    f"Expected non-canonical fact for counterfeit root call "
                    f"at line {fact.lineno}, got {fact}"
                )
                assert fact.state == BindingState.COUNTERFEIT, (
                    f"Expected COUNTERFEIT state for counterfeit root call "
                    f"at line {fact.lineno}, got {fact.state}"
                )
                # _consume_canonical must also fail for the counterfeit call.
                assert not _consume_canonical(tree, call), (
                    "Expected _consume_canonical to return False for "
                    "counterfeit root call (T1)"
                )
                return
        pytest.fail("No with-block found in T1 synthetic code")

    # =========================================================
    # T2: both branches terminate before later wrapper
    # =========================================================

    def test_t2_both_branches_terminate_no_live_predecessor(self) -> None:
        """T2: Both branches of if/else terminate before the post-join
        canonical wrapper.  The wrapper has no live predecessor and fails
        closed — ``_block_has_live_path_to`` returns ``False``."""
        tree = ast.parse(T2_BOTH_BRANCHES_TERMINATE_CODE)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                for with_stmt in ast.walk(node):
                    if isinstance(with_stmt, ast.With):
                        target_lineno = with_stmt.lineno
                        live = _block_has_live_path_to(body, target_lineno)
                        assert not live, (
                            f"Expected no live predecessor to with-block at line "
                            f"{target_lineno}, but _block_has_live_path_to returned True"
                        )
                        # _consume_canonical must also fail.
                        call = with_stmt.items[0].context_expr
                        canonical = _consume_canonical(
                            tree, call, predecessor_body=body
                        )
                        assert not canonical, (
                            "Expected _consume_canonical to return False when "
                            "no live predecessor exists (T2)"
                        )
                        return
        pytest.fail("No with-block found in T2 synthetic code")

    # =========================================================
    # T3: unbound owner
    # =========================================================

    def test_t3_unbound_owner_fails_closed(self) -> None:
        """T3: When the root module name is never imported or bound,
        the FQN call observation returns UNBOUND state, and
        ``_consume_canonical`` returns ``False``."""
        tree = ast.parse(T3_UNBOUND_OWNER_CODE)
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                call = node.items[0].context_expr
                fact = _observe_call_fact(tree, call)
                assert not fact.is_canonical(), (
                    f"Expected non-canonical fact for unbound owner at "
                    f"line {fact.lineno}, got {fact}"
                )
                assert fact.state in (
                    BindingState.UNBOUND,
                    BindingState.COUNTERFEIT,
                ), (
                    f"Expected UNBOUND or COUNTERFEIT state for unbound "
                    f"owner, got {fact.state}"
                )
                assert not _consume_canonical(tree, call), (
                    "Expected _consume_canonical to return False for unbound owner (T3)"
                )
                return
        pytest.fail("No with-block found in T3 synthetic code")

    # =========================================================
    # C1: canonical bare
    # =========================================================

    def test_c1_canonical_bare_name_call(self) -> None:
        """C1: A bare-name call with canonical import observes ``BOUND``
        canonical state and ``_consume_canonical`` returns ``True``."""
        tree = ast.parse(C1_CANONICAL_BARE_CODE)
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                call = node.items[0].context_expr
                fact = _observe_call_fact(tree, call)
                assert fact.is_canonical(), (
                    f"Expected canonical fact for canonical bare call "
                    f"at line {fact.lineno}, got {fact}"
                )
                assert fact.state == BindingState.BOUND, (
                    f"Expected BOUND state for canonical bare call, got {fact.state}"
                )
                # Verify with predecessor body.
                for func_node in ast.walk(tree):
                    if isinstance(
                        func_node,
                        (ast.FunctionDef, ast.AsyncFunctionDef),
                    ):
                        canonical = _consume_canonical(
                            tree, call, predecessor_body=func_node.body
                        )
                        assert canonical, (
                            "Expected _consume_canonical to return True "
                            "for canonical bare call (C1)"
                        )
                        break
                return
        pytest.fail("No with-block found in C1 synthetic code")

    # =========================================================
    # C2: canonical FQN
    # =========================================================

    def test_c2_canonical_fqn_call(self) -> None:
        """C2: An FQN call with canonical import observes ``BOUND``
        state and ``_consume_canonical`` returns ``True``."""
        tree = ast.parse(C2_CANONICAL_FQN_CODE)
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                call = node.items[0].context_expr
                fact = _observe_call_fact(tree, call)
                assert fact.is_canonical(), (
                    f"Expected canonical fact for canonical FQN call "
                    f"at line {fact.lineno}, got {fact}"
                )
                assert fact.state == BindingState.BOUND, (
                    f"Expected BOUND state for canonical FQN call, got {fact.state}"
                )
                for func_node in ast.walk(tree):
                    if isinstance(
                        func_node,
                        (ast.FunctionDef, ast.AsyncFunctionDef),
                    ):
                        canonical = _consume_canonical(
                            tree, call, predecessor_body=func_node.body
                        )
                        assert canonical, (
                            "Expected _consume_canonical to return True "
                            "for canonical FQN call (C2)"
                        )
                        break
                return
        pytest.fail("No with-block found in C2 synthetic code")

    # =========================================================
    # C9: counterfeit branch returns before post-join canonical wrapper
    # =========================================================

    def test_c9_counterfeit_branch_returns_before_join(self) -> None:
        """C9: A branch with a counterfeit FQN call terminates (return)
        before the join.  The post-join bare-name canonical wrapper has a
        live predecessor and is correctly identified as canonical."""
        tree = ast.parse(C9_COUNTERFEIT_RETURNS_BRANCH_CODE)
        # Distinguish the with-blocks by expression type: attribute (FQN)
        # vs. bare-name call.
        counterfeit_call: ast.Call | None = None
        canonical_call: ast.Call | None = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.With):
                continue
            call = node.items[0].context_expr
            if (
                isinstance(call.func, ast.Attribute)
                and call.func.attr == _OPERATOR_ACCESS_CM_NAME
            ):
                counterfeit_call = call
            elif (
                isinstance(call.func, ast.Name)
                and call.func.id == _OPERATOR_ACCESS_CM_NAME
            ):
                canonical_call = call
        assert counterfeit_call is not None, (
            "C9: expected a counterfeit (attribute) with-block"
        )
        assert canonical_call is not None, (
            "C9: expected a canonical (bare-name) with-block"
        )
        # Validate counterfeit call.
        first_fact = _observe_call_fact(tree, counterfeit_call)
        assert not first_fact.is_canonical(), (
            f"Expected non-canonical fact for counterfeit call, got {first_fact}"
        )
        # Validate canonical call.
        second_fact = _observe_call_fact(tree, canonical_call)
        assert second_fact.is_canonical(), (
            f"Expected canonical fact for post-join call, got {second_fact}"
        )
        # Post-join call has a live predecessor.
        for func_node in ast.walk(tree):
            if isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                canonical = _consume_canonical(
                    tree, canonical_call, predecessor_body=func_node.body
                )
                assert canonical, (
                    "Expected _consume_canonical to return True for "
                    "post-join canonical call (C9)"
                )
                break

    # =========================================================
    # C10: counterfeit branch raises before post-join canonical wrapper
    # =========================================================

    def test_c10_counterfeit_branch_raises_before_join(self) -> None:
        """C10: Same pattern as C9 but the counterfeit branch uses
        ``raise`` instead of ``return``.  The post-join canonical wrapper
        still has a live predecessor (the else path)."""
        tree = ast.parse(C10_COUNTERFEIT_RAISES_BRANCH_CODE)
        counterfeit_call: ast.Call | None = None
        canonical_call: ast.Call | None = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.With):
                continue
            call = node.items[0].context_expr
            if (
                isinstance(call.func, ast.Attribute)
                and call.func.attr == _OPERATOR_ACCESS_CM_NAME
            ):
                counterfeit_call = call
            elif (
                isinstance(call.func, ast.Name)
                and call.func.id == _OPERATOR_ACCESS_CM_NAME
            ):
                canonical_call = call
        assert counterfeit_call is not None, (
            "C10: expected a counterfeit (attribute) with-block"
        )
        assert canonical_call is not None, (
            "C10: expected a canonical (bare-name) with-block"
        )
        first_fact = _observe_call_fact(tree, counterfeit_call)
        assert not first_fact.is_canonical(), (
            f"Expected non-canonical fact for counterfeit raise call, got {first_fact}"
        )
        second_fact = _observe_call_fact(tree, canonical_call)
        assert second_fact.is_canonical(), (
            f"Expected canonical fact for post-join call, got {second_fact}"
        )
        for func_node in ast.walk(tree):
            if isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                canonical = _consume_canonical(
                    tree, canonical_call, predecessor_body=func_node.body
                )
                assert canonical, (
                    "Expected _consume_canonical to return True for "
                    "post-join canonical call (C10)"
                )
                break

    # =========================================================
    # C11: nested return does not terminate outer canonical path
    # =========================================================

    def test_c11_nested_return_does_not_terminate_outer(self) -> None:
        """C11: A ``return`` inside a nested function is isolated — it
        does NOT terminate the outer scope's canonical path.  The outer
        canonical wrapper still has a live predecessor."""
        tree = ast.parse(C11_NESTED_RETURN_ISOLATED_CODE)
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                call = node.items[0].context_expr
                fact = _observe_call_fact(tree, call)
                assert fact.is_canonical(), (
                    f"Expected canonical fact for outer call despite "
                    f"nested return, got {fact}"
                )
                # Only the outer (forward) function body should be
                # checked — the inner function's return is isolated.
                outer_func: ast.FunctionDef | None = None
                for func_node in ast.walk(tree):
                    if (
                        isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and func_node.name == "forward"
                    ):
                        outer_func = func_node
                        break
                assert outer_func is not None, "C11: expected 'forward' function"
                body_live = _block_has_live_path_to(outer_func.body, call.lineno)
                assert body_live, (
                    "Expected live predecessor in outer scope "
                    "despite nested return (C11)"
                )
                return
        pytest.fail("No with-block found in C11 synthetic code")


# =========================================================================
# SA88a.1 Phase 2 — Synthetic test code (owner cells, global/nonlocal lifetime)
# =========================================================================

# R1: global redirect canonical helper -> counterfeit
R1_GLOBAL_REDIRECT_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    global operator_access_migration
    operator_access_migration = lambda x: None
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# R2: nonlocal redirect
R2_NONLOCAL_REDIRECT_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    operator_access_migration = lambda x: None
    def inner(schema_editor):
        nonlocal operator_access_migration
        operator_access_migration = lambda y: y
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )
    inner(schema_editor)
"""

# N1: global redirect of FQN root
N1_GLOBAL_REDIRECT_FQN_ROOT_CODE = """
import quickscale_modules_orgs

def forward(apps, schema_editor):
    global quickscale_modules_orgs
    quickscale_modules_orgs = "fake"
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# O1: inner defined under canonical owner, outer rebounds before inner call
O1_OUTER_REBOUND_BEFORE_CALL_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    def inner(schema_editor):
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )
    operator_access_migration = lambda x: None
    inner(schema_editor)
"""

# O2: direct nonlocal-mutator before target callback
O2_NONLOCAL_MUTATOR_BEFORE_TARGET_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    operator_access_migration = lambda x: None
    def mutator():
        nonlocal operator_access_migration
        operator_access_migration = lambda y: y
    def target(schema_editor):
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )
    mutator()
    target(schema_editor)
"""

# O3: direct global-mutator before target callback
O3_GLOBAL_MUTATOR_BEFORE_TARGET_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    global operator_access_migration
    operator_access_migration = lambda x: None
    def target(schema_editor):
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )
    target(schema_editor)
"""

# C3: global declaration reads canonical module without write
C3_GLOBAL_NO_WRITE_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    global operator_access_migration
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# C4: global counterfeit then every-path canonical owner import
C4_GLOBAL_COUNTERFEIT_THEN_RESTORE_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    global operator_access_migration
    operator_access_migration = lambda x: None
    from quickscale_modules_orgs.tenancy import operator_access_migration
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# C5: nonlocal counterfeit then canonical owner import
C5_NONLOCAL_COUNTERFEIT_THEN_RESTORE_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    operator_access_migration = lambda x: None
    def inner():
        nonlocal operator_access_migration
        operator_access_migration = lambda y: y
    from quickscale_modules_orgs.tenancy import operator_access_migration
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# C6: outer rebind to canonical before inner direct call
C6_CANONICAL_BEFORE_INNER_CALL_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    from quickscale_modules_orgs.tenancy import operator_access_migration

    def inner(schema_editor):
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )

    inner(schema_editor)
"""

# C7: global mutator, canonical restorer, then target in proven order
C7_GLOBAL_MUTATE_RESTORE_TARGET_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    global operator_access_migration
    operator_access_migration = lambda x: None
    import quickscale_modules_orgs.tenancy
    from quickscale_modules_orgs.tenancy import operator_access_migration
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# O4: called sibling nonlocal mutator before target
O4_CALLED_SIBLING_NONLOCAL_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    operator_access_migration = lambda x: None
    def mutator():
        nonlocal operator_access_migration
        operator_access_migration = lambda y: y
    def target(schema_editor):
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )
    mutator()
    target(schema_editor)
"""

# O5: uncalled sibling nonlocal mutator (positive control — clean)
O5_UNCALLED_NONLOCAL_MUTATOR_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    operator_access_migration = lambda x: None
    def mutator():
        nonlocal operator_access_migration
        operator_access_migration = lambda y: y
    from quickscale_modules_orgs.tenancy import operator_access_migration
    def target(schema_editor):
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )
    target(schema_editor)
    # mutator is NEVER called — its nonlocal mutation never executes.
"""

# T6: counterfeit-before-raise in try body, handler restores canonical
T6_COUNTERFEIT_BEFORE_RAISE_RESTORE_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    try:
        operator_access_migration = lambda x: None
        raise ValueError()
    except ValueError:
        from quickscale_modules_orgs.tenancy import operator_access_migration
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# T7: called sibling global mutator — global declaration in nested function called before target
T7_CALLED_SIBLING_GLOBAL_MUTATOR_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    def mutator():
        global operator_access_migration
        operator_access_migration = lambda x: None
    def target(schema_editor):
        with operator_access_migration(schema_editor):
            schema_editor.execute(
                "UPDATE t SET organization_id = "
                "(SELECT id FROM other WHERE other.x = t.x)"
            )
    mutator()
    target(schema_editor)
"""


class TestSA88aPhase2OwnerLifetime:
    """Phase 2 owner-cell, global/nonlocal lifetime, and restoration proofs.

    These tests prove the analyzer correctly handles:
    - ``global`` declarations that redirect assignments to the module cell
      (R1, N1, O3)
    - ``nonlocal`` declarations that redirect assignments to the nearest
      enclosing function cell (R2, O2)
    - Compile-time local scope with outer rebound before inner call (O1)
    - Positive controls where canonical restoration executes on every
      live path before the wrapper call (C3-C7)

    Negatives go through ``check_migration_source`` and assert violations
    in both ``shadowing`` and ``ungated-raw-sql`` categories.
    Controls assert exactly zero violations.
    """

    # =========================================================
    # R1: global redirect canonical helper -> counterfeit
    # =========================================================

    def test_r1_global_redirect_counterfeit(self) -> None:
        """R1: ``global operator_access_migration`` followed by an
        assignment redirects the module cell to counterfeit.  Exact
        categories asserted."""
        violations = check_migration_source(R1_GLOBAL_REDIRECT_CODE)
        cats = sorted(v.get("category") for v in violations)
        assert cats == ["shadowing", "ungated-raw-sql"], (
            f"R1: expected exact categories [shadowing, ungated-raw-sql], "
            f"got {cats}: {violations}"
        )
        assert len([v for v in violations if v.get("category") == "shadowing"]) == 1, (
            f"R1: expected exactly 1 shadowing, got {violations}"
        )
        assert (
            len([v for v in violations if v.get("category") == "ungated-raw-sql"]) == 1
        ), f"R1: expected exactly 1 ungated-raw-sql, got {violations}"

    # =========================================================
    # R2: nonlocal redirect
    # =========================================================

    def test_r2_nonlocal_redirect_counterfeit(self) -> None:
        """R2: ``nonlocal operator_access_migration`` in a nested
        function redirects assignment to the enclosing function's cell.
        Exact categories asserted."""
        violations = check_migration_source(R2_NONLOCAL_REDIRECT_CODE)
        cats = sorted(v.get("category") for v in violations)
        assert cats == ["shadowing", "ungated-raw-sql"], (
            f"R2: expected exact categories [shadowing, ungated-raw-sql], "
            f"got {cats}: {violations}"
        )
        assert len([v for v in violations if v.get("category") == "shadowing"]) == 1, (
            f"R2: expected exactly 1 shadowing, got {violations}"
        )
        assert (
            len([v for v in violations if v.get("category") == "ungated-raw-sql"]) == 1
        ), f"R2: expected exactly 1 ungated-raw-sql, got {violations}"

    # =========================================================
    # N1: global redirect of FQN root
    # =========================================================

    def test_n1_global_redirect_fqn_root(self) -> None:
        """N1: ``global quickscale_modules_orgs`` followed by assignment
        makes the FQN root counterfeit.  Shadowing and ungated-raw-sql
        violations must appear."""
        violations = check_migration_source(N1_GLOBAL_REDIRECT_FQN_ROOT_CODE)
        shadow = [v for v in violations if v.get("category") == "shadowing"]
        raw = [v for v in violations if v.get("category") == "ungated-raw-sql"]
        assert len(shadow) >= 1, (
            f"N1: expected >=1 shadowing violation, got {len(shadow)}: {violations}"
        )
        assert len(raw) >= 1, (
            f"N1: expected >=1 ungated-raw-sql violation, got {len(raw)}: {violations}"
        )

    # =========================================================
    # O1: outer rebounds before inner call
    # =========================================================

    def test_o1_outer_rebound_before_inner_call(self) -> None:
        """O1: An inner function defined under a canonical owner has
        its outer scope rebound to counterfeit before the inner call.
        Shadowing and ungated-raw-sql violations must appear."""
        violations = check_migration_source(O1_OUTER_REBOUND_BEFORE_CALL_CODE)
        shadow = [v for v in violations if v.get("category") == "shadowing"]
        raw = [v for v in violations if v.get("category") == "ungated-raw-sql"]
        assert len(shadow) >= 1, (
            f"O1: expected >=1 shadowing violation, got {len(shadow)}: {violations}"
        )
        assert len(raw) >= 1, (
            f"O1: expected >=1 ungated-raw-sql violation, got {len(raw)}: {violations}"
        )

    # =========================================================
    # O2: nonlocal mutator before target call
    # =========================================================

    def test_o2_nonlocal_mutator_before_target(self) -> None:
        """O2: A nonlocal mutator runs before the target function.
        Exact categories asserted."""
        violations = check_migration_source(O2_NONLOCAL_MUTATOR_BEFORE_TARGET_CODE)
        cats = sorted(v.get("category") for v in violations)
        assert cats == ["shadowing", "ungated-raw-sql"], (
            f"O2: expected exact categories [shadowing, ungated-raw-sql], "
            f"got {cats}: {violations}"
        )
        assert len([v for v in violations if v.get("category") == "shadowing"]) == 1, (
            f"O2: expected exactly 1 shadowing, got {violations}"
        )
        assert (
            len([v for v in violations if v.get("category") == "ungated-raw-sql"]) == 1
        ), f"O2: expected exactly 1 ungated-raw-sql, got {violations}"

    # =========================================================
    # O3: global mutator before target call
    # =========================================================

    def test_o3_global_mutator_before_target(self) -> None:
        """O3: A global mutator changes the module cell before the
        target runs.  Exact categories asserted."""
        violations = check_migration_source(O3_GLOBAL_MUTATOR_BEFORE_TARGET_CODE)
        cats = sorted(v.get("category") for v in violations)
        assert cats == ["shadowing", "ungated-raw-sql"], (
            f"O3: expected exact categories [shadowing, ungated-raw-sql], "
            f"got {cats}: {violations}"
        )
        assert len([v for v in violations if v.get("category") == "shadowing"]) == 1, (
            f"O3: expected exactly 1 shadowing, got {violations}"
        )
        assert (
            len([v for v in violations if v.get("category") == "ungated-raw-sql"]) == 1
        ), f"O3: expected exactly 1 ungated-raw-sql, got {violations}"

    # =========================================================
    # C3: global declaration reads canonical module without write
    # =========================================================

    def test_c3_global_no_write_clean(self) -> None:
        """C3: ``global operator_access_migration`` without a subsequent
        assignment preserves the module-level canonical import.  Zero
        violations."""
        violations = check_migration_source(C3_GLOBAL_NO_WRITE_CODE)
        assert len(violations) == 0, (
            f"C3: expected 0 violations, got {len(violations)}: {violations}"
        )

    # =========================================================
    # C4: global counterfeit then every-path canonical owner import
    # =========================================================

    def test_c4_global_counterfeit_then_restore_clean(self) -> None:
        """C4: Global counterfeit assignment followed by a canonical
        import restoration function before the use.  The restoration
        (canonical-import) is the last mutation so the effective
        binding is canonical.  Zero violations."""
        violations = check_migration_source(C4_GLOBAL_COUNTERFEIT_THEN_RESTORE_CODE)
        assert len(violations) == 0, (
            f"C4: expected 0 violations, got {len(violations)}: {violations}"
        )

    # =========================================================
    # C5: nonlocal counterfeit then canonical owner import
    # =========================================================

    def test_c5_nonlocal_counterfeit_then_restore_clean(self) -> None:
        """C5: Nonlocal counterfeit assignment in inner function
        followed by a canonical import restoration in the outer
        function before the wrapper use.  The restoration is the
        last binding in the scope.  Zero violations."""
        violations = check_migration_source(C5_NONLOCAL_COUNTERFEIT_THEN_RESTORE_CODE)
        assert len(violations) == 0, (
            f"C5: expected 0 violations, got {len(violations)}: {violations}"
        )

    # =========================================================
    # C6: outer rebind to canonical before inner direct call
    # =========================================================

    def test_c6_canonical_before_inner_call_clean(self) -> None:
        """C6: An inner function references the name which is
        restored to canonical in the outer scope before the call.
        The effective binding is canonical.  Zero violations."""
        violations = check_migration_source(C6_CANONICAL_BEFORE_INNER_CALL_CODE)
        assert len(violations) == 0, (
            f"C6: expected 0 violations, got {len(violations)}: {violations}"
        )

    # =========================================================
    # C7: global mutator, canonical restorer, then target
    # =========================================================

    def test_c7_global_mutate_restore_target_clean(self) -> None:
        """C7: Global mutator + canonical import restoration before
        the with-block.  The restoration (canonical-import) is the
        last mutation in the global owner cell.  Zero violations."""
        violations = check_migration_source(C7_GLOBAL_MUTATE_RESTORE_TARGET_CODE)
        assert len(violations) == 0, (
            f"C7: expected 0 violations, got {len(violations)}: {violations}"
        )

    # =========================================================
    # O4: called sibling nonlocal mutator
    # =========================================================

    def test_o4_called_sibling_nonlocal_mutator(self) -> None:
        """O4: Sibling function with nonlocal declaration is CALLED
        before the target.  Exact categories asserted."""
        violations = check_migration_source(O4_CALLED_SIBLING_NONLOCAL_CODE)
        cats = sorted(v.get("category") for v in violations)
        assert cats == ["shadowing", "ungated-raw-sql"], (
            f"O4: expected exact categories [shadowing, ungated-raw-sql], "
            f"got {cats}: {violations}"
        )
        assert len([v for v in violations if v.get("category") == "shadowing"]) == 1, (
            f"O4: expected exactly 1 shadowing, got {violations}"
        )
        assert (
            len([v for v in violations if v.get("category") == "ungated-raw-sql"]) == 1
        ), f"O4: expected exactly 1 ungated-raw-sql, got {violations}"

    # =========================================================
    # O5: uncalled sibling nonlocal mutator (positive control)
    # =========================================================

    def test_o5_uncalled_nonlocal_mutator_clean(self) -> None:
        """O5: Sibling function with nonlocal is defined but NEVER
        called.  Zero violations — positive control proving uncalled
        mutators do NOT pollute the reaching state."""
        violations = check_migration_source(O5_UNCALLED_NONLOCAL_MUTATOR_CODE)
        assert len(violations) == 0, (
            f"O5: expected 0 violations, got {len(violations)}: {violations}"
        )
        assert not any(
            v.get("category")
            in (
                "shadowing",
                "ungated-raw-sql",
                "ungated-orm-write",
                "ungated-runsql",
                "wrong-editor",
            )
            for v in violations
        ), (
            f"O5: expected only clean run, got categories: "
            f"{[v.get('category') for v in violations]}"
        )

    # =========================================================
    # T6: counterfeit-before-raise / canonical-restoration
    # =========================================================

    def test_t6_counterfeit_before_raise_then_canonical_restore(self) -> None:
        """T6: try body assigns counterfeit then raises.  The except
        handler imports canonical again — proving the try-body state
        propagates through the exception edge.  Zero violations."""
        violations = check_migration_source(T6_COUNTERFEIT_BEFORE_RAISE_RESTORE_CODE)
        assert len(violations) == 0, (
            f"T6: expected 0 violations, got {len(violations)}: {violations}"
        )
        assert not any(
            v.get("category")
            in (
                "shadowing",
                "ungated-raw-sql",
                "ungated-orm-write",
                "ungated-runsql",
                "wrong-editor",
            )
            for v in violations
        )

    # =========================================================
    # T7: called sibling global mutator
    # =========================================================

    def test_t7_called_sibling_global_mutator(self) -> None:
        """T7: Sibling function with ``global operator_access_migration``
        is CALLED before the target.  Exact categories asserted."""
        violations = check_migration_source(T7_CALLED_SIBLING_GLOBAL_MUTATOR_CODE)
        cats = sorted(v.get("category") for v in violations)
        assert cats == ["shadowing", "ungated-raw-sql"], (
            f"T7: expected exact categories [shadowing, ungated-raw-sql], "
            f"got {cats}: {violations}"
        )


# =========================================================================
# SA88a.1 Phase 3 — Synthetic test code (conditionals, loops, try, match)
# =========================================================================

# R3: incoming canonical with counterfeit on one if path
R3_ONE_IF_PATH_COUNTERFEIT_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    if some_condition:
        operator_access_migration = lambda x: None
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# R4a: if-branch canonical, else-branch counterfeit
R4A_IF_CANONICAL_ELSE_COUNTERFEIT_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    if some_condition:
        from quickscale_modules_orgs.tenancy import operator_access_migration
    else:
        operator_access_migration = lambda x: None
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# R4b: if-branch counterfeit, else-branch canonical (reversed order)
R4B_IF_COUNTERFEIT_ELSE_CANONICAL_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    if some_condition:
        operator_access_migration = lambda x: None
    else:
        from quickscale_modules_orgs.tenancy import operator_access_migration
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# N2: module branch with canonical/counterfeit FQN root
N2_MODULE_BRANCH_COUNTERFEIT_FQN_ROOT_CODE = """
import quickscale_modules_orgs

if some_condition:
    quickscale_modules_orgs = "fake"

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# S1: canonical import in potentially zero-trip loop
S1_CANONICAL_IN_ZERO_TRIP_LOOP_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    for item in items:
        from quickscale_modules_orgs.tenancy import operator_access_migration
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# S2: short-circuit/conditional NamedExpr counterfeit
S2_NAMEDEXPR_COUNTERFEIT_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    if (oam := operator_access_migration) is not None:
        pass
    if some_condition and (operator_access_migration := lambda x: None):
        pass
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# S3: try normal canonical vs handler counterfeit
S3_TRY_CANONICAL_AND_HANDLER_COUNTERFEIT_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    try:
        from quickscale_modules_orgs.tenancy import operator_access_migration
    except ValueError:
        operator_access_migration = lambda x: None
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# S4: match canonical vs counterfeit/no-match
S4_MATCH_CANONICAL_AND_COUNTERFEIT_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    match something:
        case 1:
            from quickscale_modules_orgs.tenancy import operator_access_migration
        case 2:
            operator_access_migration = lambda x: None
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# S5: comprehension owner-directed NamedExpr with zero iteration
S5_COMPREHENSION_NAMEDEXPR_ZERO_ITER_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    _ = [x for item in items if (operator_access_migration := item)]
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# C8: both branches canonical
C8_BOTH_BRANCHES_CANONICAL_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    if some_condition:
        from quickscale_modules_orgs.tenancy import operator_access_migration
    else:
        from quickscale_modules_orgs.tenancy import operator_access_migration
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# C12: unconditional canonical import after mixed join
C12_UNCONDITIONAL_IMPORT_AFTER_MIXED_JOIN_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    if some_condition:
        operator_access_migration = lambda x: None
    else:
        pass
    from quickscale_modules_orgs.tenancy import operator_access_migration
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# N3: module-level reversed branch (canonical in if, counterfeit in else)
N3_MODULE_BRANCH_REVERSED_CODE = """
import quickscale_modules_orgs

if some_condition:
    import quickscale_modules_orgs.tenancy
else:
    quickscale_modules_orgs = "fake"

def forward(apps, schema_editor):
    with quickscale_modules_orgs.tenancy.operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# T4: counterfeit-finally — finally block rebinds to counterfeit
T4_COUNTERFEIT_FINALLY_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    try:
        pass
    finally:
        operator_access_migration = lambda x: None
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# T5: reversed asymmetric function branch (else canonical, if counterfeit)
T5_REVERSED_ASYMMETRIC_FUNCTION_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    if some_condition:
        operator_access_migration = lambda x: None
    else:
        from quickscale_modules_orgs.tenancy import operator_access_migration
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""


class TestSA88aPhase3ConditionalTransfer:
    """Phase 3 path-sensitive reaching-state transfer for conditionals,
    loops, try, match, and comprehension/generator constructs.

    Negatives (R3, R4a/R4b, N2, S1-S5) assert both ``shadowing`` and
    ``ungated-raw-sql`` violations.  Controls (C8, C12) assert exactly
    zero violations.
    """

    # =========================================================
    # R3: incoming canonical with counterfeit on one if path
    # =========================================================

    def test_r3_one_if_path_counterfeit(self) -> None:
        """R3: Canonical import at module scope, then an if-branch
        with a counterfeit assignment.  Exact categories asserted."""
        violations = check_migration_source(R3_ONE_IF_PATH_COUNTERFEIT_CODE)
        cats = sorted(v.get("category") for v in violations)
        assert cats == ["shadowing", "ungated-raw-sql"], (
            f"R3: expected exact categories [shadowing, ungated-raw-sql], "
            f"got {cats}: {violations}"
        )
        assert len([v for v in violations if v.get("category") == "shadowing"]) == 1, (
            f"R3: expected exactly 1 shadowing, got {violations}"
        )
        assert (
            len([v for v in violations if v.get("category") == "ungated-raw-sql"]) == 1
        ), f"R3: expected exactly 1 ungated-raw-sql, got {violations}"

    # =========================================================
    # R4a: if-branch canonical, else-branch counterfeit
    # =========================================================

    def test_r4a_if_canonical_else_counterfeit(self) -> None:
        """R4a: if canonical, else counterfeit.  Exact categories."""
        violations = check_migration_source(R4A_IF_CANONICAL_ELSE_COUNTERFEIT_CODE)
        cats = sorted(v.get("category") for v in violations)
        assert cats == ["shadowing", "ungated-raw-sql"], (
            f"R4a: expected exact categories [shadowing, ungated-raw-sql], "
            f"got {cats}: {violations}"
        )
        assert len([v for v in violations if v.get("category") == "shadowing"]) == 1, (
            f"R4a: expected exactly 1 shadowing, got {violations}"
        )
        assert (
            len([v for v in violations if v.get("category") == "ungated-raw-sql"]) == 1
        ), f"R4a: expected exactly 1 ungated-raw-sql, got {violations}"

    # =========================================================
    # R4b: if-branch counterfeit, else-branch canonical
    # =========================================================

    def test_r4b_if_counterfeit_else_canonical(self) -> None:
        """R4b: if counterfeit, else canonical.  Exact categories."""
        violations = check_migration_source(R4B_IF_COUNTERFEIT_ELSE_CANONICAL_CODE)
        cats = sorted(v.get("category") for v in violations)
        assert cats == ["shadowing", "ungated-raw-sql"], (
            f"R4b: expected exact categories [shadowing, ungated-raw-sql], "
            f"got {cats}: {violations}"
        )
        assert len([v for v in violations if v.get("category") == "shadowing"]) == 1, (
            f"R4b: expected exactly 1 shadowing, got {violations}"
        )
        assert (
            len([v for v in violations if v.get("category") == "ungated-raw-sql"]) == 1
        ), f"R4b: expected exactly 1 ungated-raw-sql, got {violations}"

    # =========================================================
    # N2: module branch with canonical/counterfeit FQN root
    # =========================================================

    def test_n2_module_branch_counterfeit_fqn_root(self) -> None:
        """N2: FQN root bound at module level, then conditionally
        rebound to counterfeit in a module-level if.  The join
        state is mixed.  Violations appear."""
        violations = check_migration_source(N2_MODULE_BRANCH_COUNTERFEIT_FQN_ROOT_CODE)
        shadow = [v for v in violations if v.get("category") == "shadowing"]
        raw = [v for v in violations if v.get("category") == "ungated-raw-sql"]
        assert len(shadow) >= 1, (
            f"N2: expected >=1 shadowing, got {len(shadow)}: {violations}"
        )
        assert len(raw) >= 1, (
            f"N2: expected >=1 ungated-raw-sql, got {len(raw)}: {violations}"
        )

    # =========================================================
    # S1: canonical import in potentially zero-trip loop
    # =========================================================

    def test_s1_canonical_in_zero_trip_loop(self) -> None:
        """S1: A canonical import inside a for-loop body that may
        execute zero times.  After the loop, the reaching state is
        UNKNOWN (loop might not execute).  Violations appear."""
        violations = check_migration_source(S1_CANONICAL_IN_ZERO_TRIP_LOOP_CODE)
        shadow = [v for v in violations if v.get("category") == "shadowing"]
        raw = [v for v in violations if v.get("category") == "ungated-raw-sql"]
        assert len(shadow) >= 1, (
            f"S1: expected >=1 shadowing, got {len(shadow)}: {violations}"
        )
        assert len(raw) >= 1, (
            f"S1: expected >=1 ungated-raw-sql, got {len(raw)}: {violations}"
        )

    # =========================================================
    # S2: short-circuit/conditional NamedExpr counterfeit
    # =========================================================

    def test_s2_namedexpr_counterfeit(self) -> None:
        """S2: NamedExpr (walrus) inside a conditional makes the
        binding conditional.  The reaching state is mixed/counterfeit.
        Violations appear."""
        violations = check_migration_source(S2_NAMEDEXPR_COUNTERFEIT_CODE)
        shadow = [v for v in violations if v.get("category") == "shadowing"]
        raw = [v for v in violations if v.get("category") == "ungated-raw-sql"]
        assert len(shadow) >= 1, (
            f"S2: expected >=1 shadowing, got {len(shadow)}: {violations}"
        )
        assert len(raw) >= 1, (
            f"S2: expected >=1 ungated-raw-sql, got {len(raw)}: {violations}"
        )

    # =========================================================
    # S3: try normal canonical vs handler counterfeit
    # =========================================================

    def test_s3_try_canonical_and_handler_counterfeit(self) -> None:
        """S3: try body canonical import, except handler counterfeit
        assignment.  The join is mixed.  Violations appear."""
        violations = check_migration_source(
            S3_TRY_CANONICAL_AND_HANDLER_COUNTERFEIT_CODE
        )
        shadow = [v for v in violations if v.get("category") == "shadowing"]
        raw = [v for v in violations if v.get("category") == "ungated-raw-sql"]
        assert len(shadow) >= 1, (
            f"S3: expected >=1 shadowing, got {len(shadow)}: {violations}"
        )
        assert len(raw) >= 1, (
            f"S3: expected >=1 ungated-raw-sql, got {len(raw)}: {violations}"
        )

    # =========================================================
    # S4: match canonical vs counterfeit/no-match
    # =========================================================

    def test_s4_match_canonical_and_counterfeit(self) -> None:
        """S4: match with a canonical import in one case and a
        counterfeit in another, with no default case.  The join
        is mixed (no-match path preserves pre-match state).
        Violations appear."""
        violations = check_migration_source(S4_MATCH_CANONICAL_AND_COUNTERFEIT_CODE)
        shadow = [v for v in violations if v.get("category") == "shadowing"]
        raw = [v for v in violations if v.get("category") == "ungated-raw-sql"]
        assert len(shadow) >= 1, (
            f"S4: expected >=1 shadowing, got {len(shadow)}: {violations}"
        )
        assert len(raw) >= 1, (
            f"S4: expected >=1 ungated-raw-sql, got {len(raw)}: {violations}"
        )

    # =========================================================
    # S5: comprehension NamedExpr with zero iteration
    # =========================================================

    def test_s5_comprehension_namedexpr_zero_iteration(self) -> None:
        """S5: A comprehension using operator_access_migration in its
        iteration may execute zero times.  The binding is not canonical
        on all paths.  Violations appear."""
        violations = check_migration_source(S5_COMPREHENSION_NAMEDEXPR_ZERO_ITER_CODE)
        shadow = [v for v in violations if v.get("category") == "shadowing"]
        raw = [v for v in violations if v.get("category") == "ungated-raw-sql"]
        assert len(shadow) >= 1, (
            f"S5: expected >=1 shadowing, got {len(shadow)}: {violations}"
        )
        assert len(raw) >= 1, (
            f"S5: expected >=1 ungated-raw-sql, got {len(raw)}: {violations}"
        )

    # =========================================================
    # C8: both branches canonical
    # =========================================================

    def test_c8_both_branches_canonical_clean(self) -> None:
        """C8: Both if and else branches provide a canonical import.
        The join reaching state is BOUND on all paths.  Zero violations."""
        violations = check_migration_source(C8_BOTH_BRANCHES_CANONICAL_CODE)
        assert len(violations) == 0, (
            f"C8: expected 0 violations, got {len(violations)}: {violations}"
        )

    # =========================================================
    # C12: unconditional canonical import after mixed join
    # =========================================================

    def test_c12_unconditional_import_after_mixed_join_clean(self) -> None:
        """C12: A conditional branch has a counterfeit assignment,
        but an unconditional canonical import after the join restores
        the canonical state on all paths.  Zero violations."""
        violations = check_migration_source(
            C12_UNCONDITIONAL_IMPORT_AFTER_MIXED_JOIN_CODE
        )
        assert len(violations) == 0, (
            f"C12: expected 0 violations, got {len(violations)}: {violations}"
        )


class TestGateSyntheticProof:
    """Prove the AST gate correctly distinguishes ungated from wrapped DML
    across various edge cases."""

    # --- Raw SQL execute() tests ---

    def test_ungated_dml_is_detected(self) -> None:
        """Cross-table DML without operator_access_migration is a violation."""
        violations = check_migration_source(UNGATED_CODE)
        assert len(violations) == 1, (
            f"Expected exactly 1 violation, got {len(violations)}: {violations}"
        )

    def test_wrapped_dml_is_clean(self) -> None:
        """Cross-table DML inside operator_access_migration passes."""
        violations = check_migration_source(WRAPPED_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for wrapped code, got {len(violations)}: "
            f"{violations}"
        )

    def test_ddl_not_flagged(self) -> None:
        """DDL (ALTER TABLE, CREATE POLICY) is not flagged even with
        organization_id references or subquery syntax in policy definitions."""
        violations = check_migration_source(DDL_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for DDL, got {len(violations)}: {violations}"
        )

    def test_self_table_update_not_flagged(self) -> None:
        """UPDATE with organization_id but no subquery (self-table only) is
        not flagged — no cross-table read to protect."""
        violations = check_migration_source(SELF_UPDATE_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for self-table update, got "
            f"{len(violations)}: {violations}"
        )

    def test_read_only_sql_not_flagged(self) -> None:
        """SELECT (read-only SQL) is not flagged even when it contains
        organization_id — the gate only checks UPDATE/INSERT/DELETE."""
        violations = check_migration_source(READ_ONLY_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for read-only SQL, got "
            f"{len(violations)}: {violations}"
        )

    def test_orm_backfill_is_detected(self) -> None:
        """ORM-based backfill with individual .save() (including
        _base_manager) is now flagged by the ungated assignment-save
        detector."""
        violations = check_migration_source(NO_EXECUTE_CODE)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) >= 1, (
            f"Expected at least 1 assignment-save violation for ORM backfill, got "
            f"{len(as_violations)}: {violations}"
        )

    # --- ORM .update() tests ---

    def test_ungated_orm_update_is_detected(self) -> None:
        """ORM .update(organization_id=...) without operator_access_migration
        is a violation."""
        violations = check_migration_source(UNGATED_ORM_UPDATE_CODE)
        assert len(violations) == 1, (
            f"Expected exactly 1 ORM-update violation, got "
            f"{len(violations)}: {violations}"
        )

    def test_wrapped_orm_update_is_clean(self) -> None:
        """ORM .update(organization_id=...) inside operator_access_migration
        passes."""
        violations = check_migration_source(WRAPPED_ORM_UPDATE_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for wrapped ORM update, got "
            f"{len(violations)}: {violations}"
        )

    # --- RunSQL tests ---

    def test_ungated_runsql_is_detected(self) -> None:
        """RunSQL with cross-table DML without operator_access_migration
        is a violation."""
        violations = check_migration_source(UNGATED_RUNSQL_CODE)
        assert len(violations) == 1, (
            f"Expected exactly 1 RunSQL violation, got {len(violations)}: {violations}"
        )

    def test_wrapped_runsql_is_clean(self) -> None:
        """RunSQL with cross-table DML inside operator_access_migration
        passes."""
        violations = check_migration_source(WRAPPED_RUNSQL_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for wrapped RunSQL, got "
            f"{len(violations)}: {violations}"
        )

    # --- Dynamic SQL tests ---

    def test_dynamic_sql_with_org_id_is_detected(self) -> None:
        """Dynamic SQL (f-string) containing organization_id without
        operator_access_migration is a violation."""
        violations = check_migration_source(DYNAMIC_SQL_CODE)
        assert len(violations) == 1, (
            f"Expected exactly 1 dynamic-SQL violation, got "
            f"{len(violations)}: {violations}"
        )

    # --- Exemption tests ---

    def test_exempt_crm_code_not_flagged_when_exempt(self) -> None:
        """CRM 0009 backfill matched to the exemption ledger does not
        produce a violation when checked with module_label."""
        violations = check_migration_source(
            EXEMPT_CRM_CODE,
            filepath="0009_add_note_organization_ownership.py",
        )
        # Without module_label the gate cannot match the exemption.
        # The ORM .update() pattern IS detected.
        from_assertions = [
            v for v in violations if v.get("category") == "ungated-orm-write"
        ]
        assert len(from_assertions) >= 1, (
            f"CRM backfill should produce at least 1 ORM-update "
            f"violation when checked without exemption matching, "
            f"got {len(violations)}: {violations}"
        )

    def test_unlisted_debt_fails_as_violation(self) -> None:
        """A made-up migration with unlisted ORM update fails the gate
        — proving the exemption ledger is an allow-list, not a broad
        ignore pattern."""
        code = """
def forward(apps, schema_editor):
    MyModel.objects.filter(x=1).update(organization_id="abc")
"""
        violations = check_migration_source(code)
        ungated = [v for v in violations if "ungated" in v.get("category", "")]
        assert len(ungated) >= 1, (
            f"Unlisted debt must produce a violation, got "
            f"{len(violations)}: {violations}"
        )

    # --- UPDATE FROM tests ---

    def test_ungated_update_from_is_detected(self) -> None:
        """UPDATE ... FROM without operator_access_migration is a violation."""
        violations = check_migration_source(UNGATED_UPDATE_FROM_CODE)
        assert len(violations) == 1, (
            f"Expected exactly 1 violation for UPDATE FROM, got "
            f"{len(violations)}: {violations}"
        )

    def test_wrapped_update_from_is_clean(self) -> None:
        """UPDATE ... FROM inside operator_access_migration passes."""
        violations = check_migration_source(WRAPPED_UPDATE_FROM_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for wrapped UPDATE FROM, got "
            f"{len(violations)}: {violations}"
        )

    # --- INSERT SELECT tests ---

    def test_ungated_insert_select_is_detected(self) -> None:
        """INSERT INTO ... SELECT without operator_access_migration is
        a violation."""
        violations = check_migration_source(UNGATED_INSERT_SELECT_CODE)
        assert len(violations) == 1, (
            f"Expected exactly 1 violation for INSERT SELECT, got "
            f"{len(violations)}: {violations}"
        )

    def test_wrapped_insert_select_is_clean(self) -> None:
        """INSERT INTO ... SELECT inside operator_access_migration passes."""
        violations = check_migration_source(WRAPPED_INSERT_SELECT_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for wrapped INSERT SELECT, got "
            f"{len(violations)}: {violations}"
        )

    # --- Category-specific exemption tests ---

    def test_exempt_crm_code_clean_when_matched_with_module_label(self) -> None:
        """CRM 0009 backfill matched with correct module_label produces
        no violations — the SA84 exemption correctly waives the
        ungated-orm-write category."""
        violations = check_migration_source(
            EXEMPT_CRM_CODE,
            filepath=(
                "quickscale_modules/crm/src/"
                "quickscale_modules_crm/migrations/"
                "0009_add_note_organization_ownership.py"
            ),
            module_label="quickscale_modules_crm",
        )
        assert len(violations) == 0, (
            f"Expected 0 violations when CRM exemption matched with "
            f"module_label, got {len(violations)}: {violations}"
        )

    def test_exempt_symbol_other_category_not_waived(self) -> None:
        """A raw SQL execute inside the same exempt symbol is NOT waived
        — the exemption is category-specific (ungated-orm-write) and does
        not cover ungated-raw-sql violations in the same function."""
        violations = check_migration_source(
            EXEMPT_CRM_WITH_RAW_SQL_CODE,
            filepath=(
                "quickscale_modules/crm/src/"
                "quickscale_modules_crm/migrations/"
                "0009_add_note_organization_ownership.py"
            ),
            module_label="quickscale_modules_crm",
        )
        raw_sql_violations = [
            v for v in violations if v.get("category") == "ungated-raw-sql"
        ]
        assert len(raw_sql_violations) >= 1, (
            f"Expected at least 1 raw-SQL violation in the exempt symbol "
            f"(cross-category), got {len(violations)} total: {violations}"
        )
        # The ORM-update violation should also be present (not exempted
        # when module_label is missing or category differs).
        orm_violations = [
            v for v in violations if v.get("category") == "ungated-orm-write"
        ]
        # With the category-specific exemption, the ORM-update violation
        # IS waived because its category matches.
        assert len(orm_violations) == 0, (
            f"Expected 0 ORM-update violations (exempt category), got "
            f"{len(orm_violations)}: {[v for v in violations if v.get('category') == 'ungated-orm-write']}"
        )

    # --- Raw GUC tests ---

    def test_raw_guc_set_local_is_detected(self) -> None:
        """Raw SET LOCAL app.operator_access via execute() is detected
        even when inside an operator_access_migration block."""
        violations = check_migration_source(RAW_GUC_SET_LOCAL_CODE)
        guc_violations = [v for v in violations if v.get("category") == "raw-guc"]
        assert len(guc_violations) >= 1, (
            f"Expected at least 1 raw-guc violation for SET LOCAL, got "
            f"{len(guc_violations)}: {violations}"
        )

    def test_raw_guc_set_is_detected(self) -> None:
        """Raw SET app.operator_access via execute() is detected."""
        violations = check_migration_source(RAW_GUC_SET_CODE)
        guc_violations = [v for v in violations if v.get("category") == "raw-guc"]
        assert len(guc_violations) >= 1, (
            f"Expected at least 1 raw-guc violation for SET, got "
            f"{len(guc_violations)}: {violations}"
        )

    def test_raw_guc_reset_is_detected(self) -> None:
        """Raw RESET app.operator_access via execute() is detected."""
        violations = check_migration_source(RAW_GUC_RESET_CODE)
        guc_violations = [v for v in violations if v.get("category") == "raw-guc"]
        assert len(guc_violations) >= 1, (
            f"Expected at least 1 raw-guc violation for RESET, got "
            f"{len(guc_violations)}: {violations}"
        )

    def test_raw_guc_set_config_is_detected(self) -> None:
        """Raw set_config('app.operator_access', ...) via execute() is
        detected."""
        violations = check_migration_source(RAW_GUC_SET_CONFIG_CODE)
        guc_violations = [v for v in violations if v.get("category") == "raw-guc"]
        assert len(guc_violations) >= 1, (
            f"Expected at least 1 raw-guc violation for set_config, got "
            f"{len(guc_violations)}: {violations}"
        )

    def test_raw_guc_runsql_is_detected(self) -> None:
        """RunSQL with raw SET LOCAL app.operator_access is detected."""
        violations = check_migration_source(RAW_GUC_RUNSQL_CODE)
        guc_violations = [v for v in violations if v.get("category") == "raw-guc"]
        assert len(guc_violations) >= 1, (
            f"Expected at least 1 raw-guc violation for RunSQL, got "
            f"{len(guc_violations)}: {violations}"
        )

    def test_no_raw_guc_in_clean_code(self) -> None:
        """Code that uses operator_access_migration without raw GUC
        produces zero raw-guc violations."""
        violations = check_migration_source(RAW_GUC_CLEAN_CODE)
        guc_violations = [v for v in violations if v.get("category") == "raw-guc"]
        assert len(guc_violations) == 0, (
            f"Expected 0 raw-guc violations in clean code, got "
            f"{len(guc_violations)}: {guc_violations}"
        )

    # --- Canonical import tests ---

    def test_canonical_import_is_clean(self) -> None:
        """Canonical import from ``quickscale_modules_orgs.tenancy`` with
        wrapped cross-table DML is clean."""
        violations = check_migration_source(CANONICAL_IMPORT_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for canonical wrapped import case, got "
            f"{len(violations)}: {violations}"
        )

    def test_canonical_import_is_required_when_used(self) -> None:
        """Using operator_access_migration without canonical import is a
        shadowing violation."""
        violations = check_migration_source(CANONICAL_MISSING_IMPORT_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation when canonical import is "
            f"missing, got {len(shadow_violations)}: {violations}"
        )

    # --- Nested scope tests ---

    def test_nested_inner_function_ungated_code_is_detected(self) -> None:
        """Cross-table DML in a nested callback without local
        ``operator_access_migration`` is detected."""
        violations = check_migration_source(NESTED_INNER_FUNCTION_UNGATED_CODE)
        raw_violations = [
            v for v in violations if v.get("category") == "ungated-raw-sql"
        ]
        assert len(raw_violations) >= 1, (
            f"Expected at least 1 nested ungated-raw-sql violation, got "
            f"{len(violations)}: {violations}"
        )

    def test_nested_inner_function_wrapped_code_is_clean(self) -> None:
        """Nested callback must wrap cross-table DML in its own local
        ``operator_access_migration`` block."""
        violations = check_migration_source(NESTED_INNER_FUNCTION_WRAPPED_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for nested locally wrapped code, got "
            f"{len(violations)}: {violations}"
        )

    def test_nested_wrong_editor_capture_is_detected(self) -> None:
        """Nested callback capturing outer ``schema_editor`` for
        ``operator_access_migration`` is detected as wrong-editor."""
        violations = check_migration_source(NESTED_WRONG_EDITOR_CAPTURE_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        raw_sentinel_violations = [
            v
            for v in violations
            if v.get("category") in ("ungated-raw-sql", "ungated-runsql")
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for nested capture, "
            f"got {len(violations)}: {violations}"
        )
        assert len(raw_sentinel_violations) == 0, (
            f"Wrong-editor capture should remain wrapped by operator_access in the "
            f"local callback, got cross-table violations: {violations}"
        )

    # --- Wrong editor tests ---

    def test_wrong_editor_is_detected(self) -> None:
        """operator_access_migration called with a non-schema_editor
        argument is a wrong-editor violation."""
        violations = check_migration_source(WRONG_EDITOR_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation, got "
            f"{len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_keyword_argument_is_detected(self) -> None:
        """Passing editor=... to operator_access_migration is invalid."""
        violations = check_migration_source(WRONG_EDITOR_KEYWORD_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for keyword argument, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_extra_args_are_detected(self) -> None:
        """Passing extra positional args to operator_access_migration is invalid."""
        violations = check_migration_source(WRONG_EDITOR_EXTRA_ARGS_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for extra args, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_no_args_is_detected(self) -> None:
        """Calling operator_access_migration() without args is invalid."""
        violations = check_migration_source(WRONG_EDITOR_NO_ARGS_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for missing arg, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_non_name_is_detected(self) -> None:
        """Passing a non-name expression into operator_access_migration is
        detected as wrong-editor."""
        violations = check_migration_source(WRONG_EDITOR_NON_NAME_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for non-name arg, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_rebound_via_assign_is_detected(self) -> None:
        """Rebinding ``schema_editor`` via assignment before the wrapper call
        is detected as wrong-editor."""
        violations = check_migration_source(WRONG_EDITOR_REBOUND_ASSIGN_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for rebinding by Assign, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_rebound_via_tuple_is_detected(self) -> None:
        """Tuple-unpack rebinding of ``schema_editor`` is detected as
        wrong-editor."""
        violations = check_migration_source(WRONG_EDITOR_REBOUND_TUPLE_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for tuple binding, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_rebound_via_list_is_detected(self) -> None:
        """List-unpack rebinding of ``schema_editor`` is detected as
        wrong-editor."""
        violations = check_migration_source(WRONG_EDITOR_REBOUND_LIST_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for list binding, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_rebound_via_starred_is_detected(self) -> None:
        """Starred-target rebinding of ``schema_editor`` is detected as
        wrong-editor."""
        violations = check_migration_source(WRONG_EDITOR_REBOUND_STARRED_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for starred binding, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_rebound_via_with_as_is_detected(self) -> None:
        """``with ... as schema_editor`` rebinding is detected as wrong-editor."""
        violations = check_migration_source(WRONG_EDITOR_REBOUND_WITH_AS_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for with-as binding, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_rebound_via_for_is_detected(self) -> None:
        """Loop-target rebinding of ``schema_editor`` is detected as
        wrong-editor."""
        violations = check_migration_source(WRONG_EDITOR_REBOUND_FOR_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for for-loop binding, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_rebound_via_except_is_detected(self) -> None:
        """``except ... as schema_editor`` rebinding is detected as
        wrong-editor."""
        violations = check_migration_source(WRONG_EDITOR_REBOUND_EXCEPT_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for except binding, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_rebound_via_import_is_detected(self) -> None:
        """Import binding of ``schema_editor`` is detected as wrong-editor."""
        violations = check_migration_source(WRONG_EDITOR_REBOUND_IMPORT_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for import binding, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_rebound_via_function_is_detected(self) -> None:
        """Defining ``schema_editor`` as a function before use is detected."""
        violations = check_migration_source(WRONG_EDITOR_REBOUND_FUNCTION_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for function-name binding, "
            f"got {len(editor_violations)}: {violations}"
        )

    def test_wrong_editor_rebound_via_class_is_detected(self) -> None:
        """Defining ``schema_editor`` as a class before use is detected."""
        violations = check_migration_source(WRONG_EDITOR_REBOUND_CLASS_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation for class-name binding, "
            f"got {len(editor_violations)}: {violations}"
        )

    # --- Shadowing tests ---

    def test_shadowing_assignment_is_detected(self) -> None:
        """Rebinding operator_access_migration to a different function
        via assignment is detected as shadowing."""
        violations = check_migration_source(SHADOWING_ASSIGN_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for assignment, got "
            f"{len(shadow_violations)}: {violations}"
        )

    def test_shadowing_non_canonical_import_is_detected(self) -> None:
        """Importing operator_access_migration from a non-canonical module
        is detected as shadowing."""
        violations = check_migration_source(SHADOWING_IMPORT_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for import, got "
            f"{len(shadow_violations)}: {violations}"
        )

    def test_shadowing_alias_is_detected(self) -> None:
        """Importing a different symbol as operator_access_migration is
        detected as shadowing."""
        violations = check_migration_source(SHADOWING_ALIAS_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for alias, got "
            f"{len(shadow_violations)}: {violations}"
        )

    def test_canonical_fqn_call_is_accepted(self) -> None:
        """Direct canonical FQN ``quickscale_modules_orgs.tenancy.
        operator_access_migration`` is treated as canonical and clean."""
        violations = check_migration_source(CANONICAL_FQN_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for canonical FQN usage, got "
            f"{len(violations)}: {violations}"
        )

    def test_import_star_block_is_rejected(self) -> None:
        """``from quickscale_modules_orgs.tenancy import *`` is rejected when
        operator_access_migration is used."""
        violations = check_migration_source(IMPORT_STAR_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for wildcard import, got "
            f"{len(shadow_violations)}: {violations}"
        )

    def test_module_alias_counterfeit_is_rejected(self) -> None:
        """Alias-based access through ``import quickscale_modules_orgs.tenancy as``
        is not canonical."""
        violations = check_migration_source(ALIAS_MODULE_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for module alias access, got "
            f"{len(shadow_violations)}: {violations}"
        )

    # --- CR-SA88-REV-006: additional shadowing/evasion negative proofs ---

    def test_shadowing_function_def_is_detected(self) -> None:
        """Local function definition with name ``operator_access_migration``
        that shadows the canonical import is detected as shadowing.

        This is a counterfeit locally defined helper (CR-SA88-REV-006
        evasion shape).
        """
        violations = check_migration_source(SHADOWING_FUNCTION_DEF_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for function-def shadowing, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_shadowing_class_def_is_detected(self) -> None:
        """Local class definition with name ``operator_access_migration``
        that shadows the canonical import is detected as shadowing.

        This is a counterfeit locally defined helper (CR-SA88-REV-006
        evasion shape).
        """
        violations = check_migration_source(SHADOWING_CLASS_DEF_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for class-def shadowing, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_shadowing_annassign_is_detected(self) -> None:
        """Annotated assignment that rebinds ``operator_access_migration``
        is detected as shadowing.

        This is a ``local rebinding`` evasion shape (CR-SA88-REV-006).
        """
        violations = check_migration_source(SHADOWING_ANNASSIGN_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for annotated assignment, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_shadowing_walrus_is_detected(self) -> None:
        """Walrus operator (``:=``) that rebinds ``operator_access_migration``
        is detected as shadowing.

        This is a ``local rebinding`` evasion shape (CR-SA88-REV-006).
        """
        violations = check_migration_source(SHADOWING_WALRUS_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for walrus-operator rebinding, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_shadowing_parameter_is_detected(self) -> None:
        """Function parameter named ``operator_access_migration`` that shadows
        the canonical import is detected as shadowing.

        This is a ``local rebinding`` evasion shape (CR-SA88-REV-006).
        """
        violations = check_migration_source(SHADOWING_PARAMETER_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for parameter shadowing, "
            f"got {len(shadow_violations)}: {violations}"
        )

    # --- CR-SA88-REV-006: exhaustive evasion/legitimate-binding tests ---

    def test_counterfeit_root_fqn_is_rejected(self) -> None:
        """``from evil import quickscale_modules_orgs; ... FQN call`` is
        rejected because the root module name is a counterfeit binding,
        even though the dotted string textually matches the canonical FQN.
        """
        violations = check_migration_source(COUNTERFEIT_ROOT_FQN_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for counterfeit root "
            f"FQN, got {len(shadow_violations)}: {violations}"
        )

    def test_late_module_for_rebind_is_detected(self) -> None:
        """Module-level ``for``-target rebinding after the callback definition
        is detected because module-scope resolution uses the LAST binding,
        and the loop variable is active when Django later invokes the callback.
        """
        violations = check_migration_source(LATE_MODULE_FOR_REBIND_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for late module-level "
            f"for-rebind, got {len(shadow_violations)}: {violations}"
        )

    def test_late_module_assign_rebind_is_detected(self) -> None:
        """Module-level assignment rebinding after the callback definition
        is detected (same late-rebinding principle as the for-target case).
        """
        violations = check_migration_source(LATE_MODULE_ASSIGN_REBIND_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for late module-level "
            f"assign-rebind, got {len(shadow_violations)}: {violations}"
        )

    def test_late_module_annassign_rebind_is_detected(self) -> None:
        """Module-level annotated assignment rebinding after the callback
        definition is detected."""
        violations = check_migration_source(LATE_MODULE_ANNASSIGN_REBIND_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for late module-level "
            f"annassign-rebind, got {len(shadow_violations)}: {violations}"
        )

    def test_late_module_walrus_rebind_is_detected(self) -> None:
        """Module-level walrus-operator rebinding after the callback
        definition is detected."""
        violations = check_migration_source(LATE_MODULE_WALRUS_REBIND_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for late module-level "
            f"walrus-rebind, got {len(shadow_violations)}: {violations}"
        )

    def test_late_module_augassign_rebind_is_detected(self) -> None:
        """Module-level augmented assignment rebinding after the callback
        definition is detected."""
        violations = check_migration_source(LATE_MODULE_AUGASSIGN_REBIND_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for late module-level "
            f"augassign-rebind, got {len(shadow_violations)}: {violations}"
        )

    def test_late_module_function_def_rebind_is_detected(self) -> None:
        """Module-level function definition after the callback definition
        that shadows the canonical name is detected."""
        violations = check_migration_source(LATE_MODULE_FUNCTION_DEF_REBIND_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for late module-level "
            f"function-def rebind, got {len(shadow_violations)}: {violations}"
        )

    def test_late_module_class_def_rebind_is_detected(self) -> None:
        """Module-level class definition after the callback definition
        that shadows the canonical name is detected."""
        violations = check_migration_source(LATE_MODULE_CLASS_DEF_REBIND_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for late module-level "
            f"class-def rebind, got {len(shadow_violations)}: {violations}"
        )

    def test_inner_canonical_override_accepts_inner_import(self) -> None:
        """A module-level counterfeit binding overridden by an inner
        canonical import is NOT flagged (positive test for the CR-SA88-REV-006
        false positive fix)."""
        violations = check_migration_source(INNER_CANONICAL_OVERRIDE_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) == 0, (
            f"Expected 0 shadowing violations when inner canonical import "
            f"overrides outer counterfeit, got {len(shadow_violations)}: "
            f"{violations}"
        )

    def test_inner_canonical_override_nested_scope(self) -> None:
        """A nested-function canonical import that overrides a module-level
        counterfeit is not flagged."""
        violations = check_migration_source(INNER_CANONICAL_OVERRIDE_NESTED_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) == 0, (
            f"Expected 0 shadowing violations for nested inner canonical "
            f"override, got {len(shadow_violations)}: {violations}"
        )

    def test_canonical_alias_not_flagged_as_shadowing(self) -> None:
        """Creating an alias name (``op_acc_mig = operator_access_migration``)
        does not shadow the canonical name and is not flagged.  The alias is
        a different name."""
        violations = check_migration_source(CANONICAL_ASSIGN_ALIAS_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) == 0, (
            f"Expected 0 shadowing violations for canonical alias (different "
            f"name), got {len(shadow_violations)}: {violations}"
        )

    def test_param_shadowing_posonly_is_detected(self) -> None:
        """Positional-only parameter shadowing is detected (Python 3.8+
        ``/`` separator)."""
        violations = check_migration_source(PARAM_SHADOWING_POSONLY_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for positional-only "
            f"parameter, got {len(shadow_violations)}: {violations}"
        )

    def test_param_shadowing_kwonly_is_detected(self) -> None:
        """Keyword-only parameter shadowing is detected (``*`` separator)."""
        violations = check_migration_source(PARAM_SHADOWING_KWONLY_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for keyword-only "
            f"parameter, got {len(shadow_violations)}: {violations}"
        )

    def test_param_shadowing_vararg_is_detected(self) -> None:
        """Variable-length positional parameter (``*args``) shadowing is
        detected."""
        violations = check_migration_source(PARAM_SHADOWING_VARARG_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for vararg parameter, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_param_shadowing_kwarg_is_detected(self) -> None:
        """Variable-length keyword parameter (``**kwargs``) shadowing is
        detected."""
        violations = check_migration_source(PARAM_SHADOWING_KWARG_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for kwarg parameter, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_function_scope_rebind_only_affects_own_scope(self) -> None:
        """A function-scope rebind in ``forward`` shadows the canonical name
        only in that function.  ``other_func`` still sees the module-level
        canonical import (positive test)."""
        violations = check_migration_source(FUNCTION_SCOPE_REBIND_NOT_GLOBAL_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        # forward has a function-def shadowing of operator_access_migration
        # so the call inside forward uses the function-scope binding (not
        # canonical). other_func uses the module-level canonical import.
        # So we expect exactly 1 shadowing violation for forward's call.
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation (forward's call uses "
            f"local function-def name), got {len(shadow_violations)}: "
            f"{violations}"
        )

    def test_canonical_fqn_with_import_is_accepted(self) -> None:
        """Canonical FQN with proper ``import quickscale_modules_orgs``
        is accepted and produces zero violations."""
        violations = check_migration_source(CANONICAL_FQN_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for canonical FQN with import, got "
            f"{len(violations)}: {violations}"
        )

    def test_fqn_module_alias_is_rejected(self) -> None:
        """``import quickscale_modules_orgs.tenancy as tenancy`` followed by
        ``tenancy.operator_access_migration(...)`` is not the canonical FQN
        and the call is non-canonical.  The checker should flag this."""
        violations = check_migration_source(FQN_WITH_IMPORT_MODULE_ALIAS_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for module alias FQN, "
            f"got {len(shadow_violations)}: {violations}"
        )

    # --- CR-SA88-REV-006: exhaustive counterfeit-root forms ---

    def test_counterfeit_root_assign_is_rejected(self) -> None:
        """Assignment binding of ``quickscale_modules_orgs`` before FQN call
        is a counterfeit root and the FQN call is rejected."""
        violations = check_migration_source(COUNTERFEIT_ROOT_ASSIGN_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected shadowing violation for assignment counterfeit root, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_counterfeit_root_function_is_rejected(self) -> None:
        """Function definition binding of ``quickscale_modules_orgs`` before
        FQN call is a counterfeit root."""
        violations = check_migration_source(COUNTERFEIT_ROOT_FUNCTION_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected shadowing violation for function-def counterfeit root, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_counterfeit_root_class_is_rejected(self) -> None:
        """Class definition binding of ``quickscale_modules_orgs`` before
        FQN call is a counterfeit root."""
        violations = check_migration_source(COUNTERFEIT_ROOT_CLASS_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected shadowing violation for class-def counterfeit root, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_counterfeit_root_for_target_is_rejected(self) -> None:
        """For-loop target binding of ``quickscale_modules_orgs`` before
        FQN call is a counterfeit root."""
        violations = check_migration_source(COUNTERFEIT_ROOT_FOR_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected shadowing violation for for-target counterfeit root, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_counterfeit_root_withas_is_rejected(self) -> None:
        """With-as target binding of ``quickscale_modules_orgs`` before
        FQN call is a counterfeit root."""
        violations = check_migration_source(COUNTERFEIT_ROOT_WITHAS_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected shadowing violation for with-as counterfeit root, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_counterfeit_root_except_is_rejected(self) -> None:
        """Except-handler binding of ``quickscale_modules_orgs`` before
        FQN call is a counterfeit root."""
        violations = check_migration_source(COUNTERFEIT_ROOT_EXCEPT_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected shadowing violation for except counterfeit root, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_counterfeit_root_param_is_rejected(self) -> None:
        """Parameter binding of ``quickscale_modules_orgs`` before FQN call
        is a counterfeit root."""
        violations = check_migration_source(COUNTERFEIT_ROOT_PARAM_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected shadowing violation for param counterfeit root, "
            f"got {len(shadow_violations)}: {violations}"
        )

    def test_counterfeit_root_import_alias_is_rejected(self) -> None:
        """Import alias binding of ``quickscale_modules_orgs`` before FQN
        call is a counterfeit root."""
        violations = check_migration_source(COUNTERFEIT_ROOT_IMPORT_ALIAS_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected shadowing violation for import alias counterfeit root, "
            f"got {len(shadow_violations)}: {violations}"
        )

    # --- CR-SA88-REV-006: later canonical root restoration ---

    def test_counterfeit_then_canonical_root_is_accepted(self) -> None:
        """A counterfeit root followed by a later canonical
        ``import quickscale_modules_orgs.tenancy`` produces zero violations
        (module-final semantics)."""
        violations = check_migration_source(COUNTERFEIT_THEN_CANONICAL_ROOT_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations when later canonical import overrides "
            f"counterfeit root, got {len(violations)}: {violations}"
        )

    def test_counterfeit_then_canonical_root_via_import_is_accepted(self) -> None:
        """A counterfeit root followed by ``import quickscale_modules_orgs``
        restores canonical root validity (module-final semantics)."""
        violations = check_migration_source(
            COUNTERFEIT_THEN_CANONICAL_ROOT_VIA_IMPORT_CODE
        )
        assert len(violations) == 0, (
            f"Expected 0 violations when later ``import quickscale_modules_orgs`` "
            f"overrides counterfeit root, got {len(violations)}: {violations}"
        )

    def test_later_counterfeit_root_after_canonical_is_rejected(self) -> None:
        """A later assignment rebinding after the canonical import makes the
        root counterfeit at module-final state (flagged)."""
        violations = check_migration_source(LATER_COUNTERFEIT_ROOT_AFTER_CANONICAL_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected shadowing violation when later binding makes FQN root "
            f"counterfeit, got {len(shadow_violations)}: {violations}"
        )

    # --- CR-SA88-REV-006: star import ordering ---

    def test_star_import_then_canonical_is_clean(self) -> None:
        """Star import followed by exact canonical import at module level
        produces zero shadowing violations (module-final semantics)."""
        violations = check_migration_source(STAR_IMPORT_THEN_CANONICAL_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) == 0, (
            f"Expected 0 shadowing violations when exact canonical follows "
            f"star import, got {len(shadow_violations)}: {violations}"
        )

    # --- CR-SA88-REV-006: function-scope compile-time-local rule ---

    def test_use_before_function_local_bind_is_rejected(self) -> None:
        """A canonical import at module scope followed by an assignment in
        the function makes the name LOCAL at compile time.  A use before the
        assignment must NOT fall through to the module-level canonical import
        and should be flagged as unbound-local."""
        violations = check_migration_source(USE_BEFORE_FUNCTION_LOCAL_BIND_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for use before function "
            f"local bind, got {len(shadow_violations)}: {violations}"
        )

    # --- Assignment+save tests ---

    def test_ungated_assignment_save_is_detected(self) -> None:
        """obj.organization_id = x followed by obj.save() without
        operator_access_migration is detected."""
        violations = check_migration_source(ASSIGN_SAVE_UNGATED_CODE)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) >= 1, (
            f"Expected at least 1 assignment-save violation, got "
            f"{len(as_violations)}: {violations}"
        )

    def test_wrapped_assignment_save_is_clean(self) -> None:
        """obj.organization_id = x followed by obj.save() inside
        operator_access_migration passes."""
        violations = check_migration_source(ASSIGN_SAVE_WRAPPED_CODE)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) == 0, (
            f"Expected 0 assignment-save violations when wrapped, got "
            f"{len(as_violations)}: {violations}"
        )

    def test_ungated_assignment_save_base_manager_is_detected(self) -> None:
        """A _base_manager assignment-save pattern is still detected as
        ungated and not exempted by earlier ORM-manager assumptions."""
        violations = check_migration_source(ASSIGN_SAVE_BASE_MANAGER_CODE)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) >= 1, (
            f"Expected at least 1 assignment-save violation with _base_manager, got "
            f"{len(as_violations)}: {violations}"
        )

    def test_outer_wrapped_inner_ungated_assignment_save_is_detected(self) -> None:
        """Wrapping the outer callback does not satisfy inner nested callbacks.

        Inner callback operations require their own local
        ``operator_access_migration`` scope.
        """
        violations = check_migration_source(
            ASSIGN_SAVE_OUTER_WRAPPED_INNER_UNGATED_CODE
        )
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) >= 1, (
            f"Expected at least 1 nested inner assignment-save violation, got "
            f"{len(as_violations)}: {violations}"
        )

    def test_outer_and_inner_wrapped_assignment_save_is_clean(self) -> None:
        """Nested callbacks are clean when both outer and inner scopes are
        properly wrapped with their own local callback argument."""
        violations = check_migration_source(
            ASSIGN_SAVE_OUTER_WRAPPED_INNER_WRAPPED_CODE
        )
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) == 0, (
            f"Expected 0 assignment-save violations when inner callback is also "
            f"wrapped, got {len(as_violations)}: {violations}"
        )

    def test_ungated_assignment_save_update_fields_is_detected(self) -> None:
        """obj.organization_id = x followed by
        obj.save(update_fields=[...]) without operator_access_migration
        is detected."""
        violations = check_migration_source(ASSIGN_SAVE_UPDATE_FIELDS_CODE)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) >= 1, (
            f"Expected at least 1 assignment-save violation with "
            f"update_fields, got {len(as_violations)}: {violations}"
        )

    def test_ungated_assignment_save_far_apart_is_detected(self) -> None:
        """Assignments and same-receiver saves far apart in a function are still
        detected."""
        violations = check_migration_source(ASSIGN_SAVE_FAR_APART_CODE)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) >= 1, (
            f"Expected at least 1 assignment-save violation for far-apart pair, "
            f"got {len(as_violations)}: {violations}"
        )

    def test_ungated_assignment_save_annassign_is_detected(self) -> None:
        """Annotated assignment to ``organization_id`` before save is detected."""
        violations = check_migration_source(ASSIGN_SAVE_ANNASSIGN_CODE)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) >= 1, (
            f"Expected at least 1 assignment-save violation for annassign, "
            f"got {len(as_violations)}: {violations}"
        )

    def test_assignment_save_different_receivers_are_not_flagged(self) -> None:
        """Assignment and save on different receivers are not paired."""
        violations = check_migration_source(ASSIGN_SAVE_DIFFERENT_RECEIVER_CODE)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) == 0, (
            f"Expected 0 assignment-save violations for different receivers, "
            f"got {len(as_violations)}: {as_violations}"
        )


# =========================================================================
# CRM 0009 exact exemption proof
# =========================================================================


class TestCRMExemptionContentProof:
    """Prove the CRM 0009 exemption ledger contains exactly the two
    expected symbols with ``ungated-orm-write`` category, owned by SA84,
    and no other exemptions exist in the ledger."""

    def test_exact_crm_exemption_content(self) -> None:
        """CRM 0009 exemption has exactly:
        - symbol ``_backfill_contactnote_org`` with category
          ``ungated-orm-write`` owned by SA84
        - symbol ``_backfill_dealnote_org`` with category
          ``ungated-orm-write`` owned by SA84
        - No other entries for CRM 0009.
        """
        crm_key = (
            "quickscale_modules_crm",
            "0009_add_note_organization_ownership",
        )
        assert crm_key in SA88_DEBT_EXEMPTIONS, (
            "CRM 0009 key not found in SA88_DEBT_EXEMPTIONS"
        )
        entries = SA88_DEBT_EXEMPTIONS[crm_key]

        assert len(entries) == 2, (
            f"Expected exactly 2 exemption entries for CRM 0009, "
            f"got {len(entries)}: {entries}"
        )

        # Check first symbol
        e0 = entries[0]
        assert e0["symbol"] == "_backfill_contactnote_org", (
            f"Expected first symbol '_backfill_contactnote_org', "
            f"got '{e0.get('symbol')}'"
        )
        assert e0["category"] == "ungated-orm-write", (
            f"Expected category 'ungated-orm-write', got '{e0.get('category')}'"
        )
        assert "SA84" in e0.get("owns", ""), (
            f"Expected owns field mentioning SA84, got '{e0.get('owns')}'"
        )

        # Check second symbol
        e1 = entries[1]
        assert e1["symbol"] == "_backfill_dealnote_org", (
            f"Expected second symbol '_backfill_dealnote_org', got '{e1.get('symbol')}'"
        )
        assert e1["category"] == "ungated-orm-write", (
            f"Expected category 'ungated-orm-write', got '{e1.get('category')}'"
        )
        assert "SA84" in e1.get("owns", ""), (
            f"Expected owns field mentioning SA84, got '{e1.get('owns')}'"
        )

        # No other CRM 0009 entries
        assert len(entries) == 2, "Extra entries found in CRM 0009 exemption"


# =========================================================================
# Manifested-uninstalled module inventory
# =========================================================================


class TestManifestedModuleInventory:
    """Prove the gate can inventory all manifested quickscale_modules
    migration directories independent of INSTALLED_APPS."""

    def test_manifested_dirs_are_found(self) -> None:
        """``get_all_module_migration_dirs`` returns at least one
        migration directory, proving filesystem-based discovery works
        regardless of INSTALLED_APPS."""
        dirs = get_all_module_migration_dirs()
        assert len(dirs) >= 1, (
            f"Expected at least 1 migration directory, got {len(dirs)}"
        )
        # Each dir must exist and be a directory
        for d in dirs:
            assert d.is_dir(), f"Migration directory {d} does not exist"

    def test_manifested_dirs_migration_files_parse(self) -> None:
        """Every migration file in all manifested directories is valid
        Python and can be parsed by check_migration_source without
        syntax errors."""
        dirs = get_all_module_migration_dirs()
        all_syntax_errors: list[str] = []
        migration_read_errors: list[dict] = []
        for d in dirs:
            for py_file in sorted(d.glob("[0-9]*.py")):
                source, read_errors = _read_migration_source_with_read_error(py_file)
                migration_read_errors.extend(read_errors)
                if source is None:
                    continue
                violations = check_migration_source(
                    source,
                    str(py_file),
                )
                for v in violations:
                    if "Syntax error" in v.get("message", ""):
                        all_syntax_errors.append(f"{py_file}: {v['message']}")
        read_error_lines = [
            f"{v['filepath']}:{v['line']} [{v.get('category')}] {v['message']}"
            for v in migration_read_errors
        ]
        if read_error_lines:
            pytest.fail(
                f"{len(read_error_lines)} migration file(s) were unreadable:\n"
                + "\n".join(read_error_lines)
            )
        if all_syntax_errors:
            pytest.fail(
                f"{len(all_syntax_errors)} file(s) have syntax errors:\n"
                + "\n".join(all_syntax_errors)
            )

    def test_discovery_discovers_src_and_flat_module_layouts(
        self,
        tmp_path: Path,
    ) -> None:
        """Manifest discovery resolves migrations for both ``src`` and
        package-level module layouts."""
        src_layout = tmp_path / "mod-src"
        src_layout.mkdir()
        (src_layout / "module.yml").write_text('{"name": "mod-src"}', encoding="utf-8")
        src_migrations = (
            src_layout / "src" / "quickscale_modules_mod_src" / "migrations"
        )
        src_migrations.mkdir(parents=True)
        (src_migrations / "0001_src_mod.py").write_text(
            "from django.db import migrations\n", encoding="utf-8"
        )

        flat_layout = tmp_path / "mod_flat"
        flat_layout.mkdir()
        (flat_layout / "module.yml").write_text(
            '{"name": "mod-flat"}', encoding="utf-8"
        )
        flat_migrations = flat_layout / "quickscale_modules_mod_flat" / "migrations"
        flat_migrations.mkdir(parents=True)
        (flat_migrations / "0002_flat_mod.py").write_text(
            "from django.db import migrations\n", encoding="utf-8"
        )

        dirs = get_all_module_migration_dirs(modules_root=tmp_path)
        assert len(dirs) == 2, (
            f"Expected exactly 2 discovered migration dirs, got {dirs}"
        )
        assert src_migrations.resolve() in dirs, (
            f"src-layout migrations missing: {dirs}"
        )
        assert flat_migrations.resolve() in dirs, (
            f"flat-layout migrations missing: {dirs}"
        )

    def test_discovery_respects_migration_file_glob_pattern(
        self,
        tmp_path: Path,
    ) -> None:
        """`get_all_migration_files` only returns timestamp-like Python
        migration files and ignores non-matching entries."""
        mod_dir = tmp_path / "mod-pattern"
        mod_dir.mkdir()
        (mod_dir / "module.yml").write_text('{"name": "mod-pattern"}', encoding="utf-8")
        mig_dir = mod_dir / "src" / "quickscale_modules_mod_pattern" / "migrations"
        mig_dir.mkdir(parents=True)
        (mig_dir / "0001_valid.py").write_text("from django.db import migrations\n")
        (mig_dir / "init.py").write_text("from django.db import migrations\n")
        (mig_dir / "README.txt").write_text("ignore\n")

        files = get_all_migration_files(modules_root=tmp_path)
        assert files == [mig_dir / "0001_valid.py"], (
            f"Expected only timestamp-like migration file, got: {files}"
        )

    def test_read_error_returns_diagnostic(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """OSError on file reads becomes a migration-read-error diagnostic."""
        migration_file = tmp_path / "0001_broken.py"
        migration_file.write_text(
            "from django.db import migrations\n", encoding="utf-8"
        )

        def _raise_os_error(self: Path, *args: object, **kwargs: object) -> str:
            raise OSError("boom")

        monkeypatch.setattr(Path, "read_text", _raise_os_error)
        source, errors = _read_migration_source_with_read_error(migration_file)

        assert source is None
        assert len(errors) == 1
        assert errors[0]["category"] == "migration-read-error"
        assert (
            "migration-read-error: cannot read migration file" in errors[0]["message"]
        )

    def test_read_non_os_error_is_not_swallowed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Non-OSError read failures should propagate for visibility."""
        migration_file = tmp_path / "0002_broken.py"
        migration_file.write_text(
            "from django.db import migrations\n", encoding="utf-8"
        )

        def _raise_value_error(self: Path, *args: object, **kwargs: object) -> str:
            raise ValueError("unexpected")

        monkeypatch.setattr(Path, "read_text", _raise_value_error)
        with pytest.raises(ValueError, match="unexpected"):
            _read_migration_source_with_read_error(migration_file)


# =========================================================================
# Real-tree compliance test
# =========================================================================


class TestMigrationOperatorAccessConformance:
    """Verify every shipped migration wraps cross-table DML in
    ``operator_access_migration``."""

    def _get_module_label(self, filepath: str) -> str | None:
        """Derive the Django app label from a migration file path."""
        p = Path(filepath)
        parts = p.parts
        for i, part in enumerate(parts):
            if part == "src" and i + 1 < len(parts):
                return parts[i + 1]
        return None

    def test_all_migrations_pass_conformance_gate(self) -> None:
        """Every migration file in ``quickscale_modules_*`` apps passes the
        SA88 conformance gate.

        This is the authoritative negative-proof gate: any migration that
        contains cross-table DML assigning ``organization_id`` that is NOT
        lexically enclosed by ``with operator_access_migration(...)`` fails
        this test with an actionable location report.

        Known debt exemptions in ``SA88_DEBT_EXEMPTIONS`` are allowed but
        tracked.  Any migration not in that ledger that contains ungated
        cross-table DML fails closed.
        """
        all_violations: list[dict] = []
        for filepath in get_migration_files():
            fp_str = str(filepath)
            source, read_errors = _read_migration_source_with_read_error(filepath)
            all_violations.extend(read_errors)
            if source is None:
                continue
            module_label = self._get_module_label(fp_str)
            violations = check_migration_source(source, fp_str, module_label)
            all_violations.extend(violations)

        read_violations = [
            v for v in all_violations if v.get("category") == "migration-read-error"
        ]

        if all_violations:
            msg_lines: list[str] = []
            if read_violations:
                msg_lines.extend(
                    [f"{len(read_violations)} unreadable migration file(s) found:"]
                )
                for v in read_violations:
                    msg_lines.append(
                        f"  {v['filepath']}:{v['line']} "
                        f"[{v.get('category')}] — {v['message']}"
                    )
                msg_lines.append("---")
            msg_lines.append(f"{len(all_violations)} violation(s) found:")
            for v in all_violations:
                msg_lines.append(
                    f"  {v['filepath']}:{v['line']} "
                    f"[{v.get('category', 'unknown')}] "
                    f"— {v['message']}"
                )
            pytest.fail("\n".join(msg_lines))

    def test_no_raw_guc_in_real_tree(self) -> None:
        """No migration in the installed tree contains raw GUC manipulation
        of ``app.operator_access``.

        This is a focused negative-proof gate complementing the broader
        conformance check above.  Raw GUC manipulation is always forbidden
        (non-exemptible); the ``operator_access_migration`` context manager
        is the only permitted mechanism.
        """
        raw_guc_violations: list[dict] = []
        for filepath in get_migration_files():
            fp_str = str(filepath)
            source, read_errors = _read_migration_source_with_read_error(filepath)
            raw_guc_violations.extend(read_errors)
            if source is None:
                continue
            module_label = self._get_module_label(fp_str)
            violations = check_migration_source(source, fp_str, module_label)
            for v in violations:
                if v.get("category") == "raw-guc":
                    raw_guc_violations.append(v)

        read_violations = [
            v for v in raw_guc_violations if v.get("category") == "migration-read-error"
        ]

        if raw_guc_violations:
            msg_lines: list[str] = []
            if read_violations:
                msg_lines.extend(
                    [f"{len(read_violations)} unreadable migration file(s) found:"]
                )
                for v in read_violations:
                    msg_lines.append(
                        f"  {v['filepath']}:{v['line']} "
                        f"[{v.get('category')}] — {v['message']}"
                    )
                msg_lines.append("---")
            msg_lines.append(
                f"{len(raw_guc_violations)} migration(s) contain raw GUC "
                f"manipulation of app.operator_access:"
            )
            for v in raw_guc_violations:
                msg_lines.append(f"  {v['filepath']}:{v['line']} — {v['message']}")
            pytest.fail("\n".join(msg_lines))
