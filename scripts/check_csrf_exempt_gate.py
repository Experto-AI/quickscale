#!/usr/bin/env python3
"""
SA46 — Hard-fail AST lint gate requiring csrf_exempt + _enforce_csrf/signature pair.

Scans ``quickscale_modules/*/src/`` for function and class definitions that
apply ``csrf_exempt`` (directly, via ``@method_decorator(csrf_exempt, ...)``,
or via the blog's ``@_typed_csrf_exempt`` wrapper) and verifies the same
callable (or a method of the same class) calls at least one approved
verification helper.

Approved verification helpers:
  - ``_enforce_csrf``               — explicit CSRF re-enforcement (billing/blog)
  - ``authenticate_blog_api_request`` — blog session+token auth (calls
    ``_enforce_csrf`` for session-authenticated requests)
  - ``handle_stripe_event``         — Stripe webhook signature verification
  - ``ingest_webhook_event``        — notifications HMAC signature verification

Any ``csrf_exempt``-annotated scope that lacks a call to one of these helpers
**fails CI** (exit 1).

Exit codes:
    0 — no violations found
    1 — one or more violations detected (hard-fail)
    2 — a configuration or filesystem error
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT_ENV: str = "REPO_ROOT"
_DEFAULT_REPO_ROOT: Path = Path(os.environ.get(REPO_ROOT_ENV, os.getcwd())).resolve()

MODULES_DIR_RELATIVE: Path = Path("quickscale_modules")

# Decorator names that indicate csrf_exempt is applied to the decorated node.
# This covers both Django's ``csrf_exempt`` and the blog module's
# ``_typed_csrf_exempt`` wrapper (which preserves view typing).
CSRF_EXEMPT_DECORATOR_NAMES: frozenset[str] = frozenset(
    {
        "csrf_exempt",
        "_typed_csrf_exempt",
    }
)

# Name of the ``method_decorator`` helper that can carry ``csrf_exempt`` as
# an argument (e.g. ``@method_decorator(csrf_exempt, name='dispatch')``).
METHOD_DECORATOR_NAME: str = "method_decorator"

# Approved verification helper names.
# A csrf_exempt-annotated scope must contain at least one call to one of these
# functions (direct call, not method call on an object).  These are the known
# patterns for re-enforcing CSRF or verifying a cryptographic signature.
APPROVED_VERIFICATION_HELPERS: frozenset[str] = frozenset(
    {
        "_enforce_csrf",
        "authenticate_blog_api_request",
        "handle_stripe_event",
        "ingest_webhook_event",
    }
)

# Module names that are exempt from the lint gate.
# Currently none — all modules are scanned.
EXEMPT_MODULES: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# Helper predicates
# ---------------------------------------------------------------------------


def _is_csrf_exempt_decorator(decorator: ast.expr) -> bool:
    """
    Return ``True`` if *decorator* applies ``csrf_exempt``.

    Handles:
      - ``@csrf_exempt``                         (ast.Name)
      - ``@_typed_csrf_exempt``                  (ast.Name)
      - ``@method_decorator(csrf_exempt, ...)``   (ast.Call)
    """
    if isinstance(decorator, ast.Name) and decorator.id in CSRF_EXEMPT_DECORATOR_NAMES:
        return True

    if (
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Name)
        and decorator.func.id == METHOD_DECORATOR_NAME
    ):
        # Check positional args: ``@method_decorator(csrf_exempt, ...)``
        for arg in decorator.args:
            if isinstance(arg, ast.Name) and arg.id == "csrf_exempt":
                return True
        # Check keyword values: ``@method_decorator(csrf_exempt=...)``
        # (unusual but handled for completeness)
        for kw in decorator.keywords:
            if isinstance(kw.value, ast.Name) and kw.value.id == "csrf_exempt":
                return True

    return False


def _body_contains_helper_call(body: list[ast.stmt]) -> bool:
    """
    Return ``True`` if *body* contains a direct call to an approved helper.

    Walks descendant AST nodes but **does not** descend into nested
    ``FunctionDef``, ``AsyncFunctionDef``, ``ClassDef``, or ``Lambda``
    bodies.  This prevents dead-code or deeply nested helpers from
    satisfying the pairing requirement — only helpers reachable in the
    immediate request-path handler body count.
    """
    for stmt in body:
        if _node_walks_helper_call(stmt):
            return True
    return False


def _node_walks_helper_call(node: ast.AST) -> bool:
    """
    Recursively walk *node*'s descendants looking for an approved helper call.

    **Does not descend** into ``FunctionDef``, ``AsyncFunctionDef``,
    ``ClassDef``, or ``Lambda`` boundaries.  The guard is on *node* itself
    (not just its children) so that even the internals of a nested scope are
    never inspected — helpers buried in dead or deeply nested code can never
    satisfy the csrf_exempt pairing requirement.
    """
    # Do NOT cross scope boundaries
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return False

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in APPROVED_VERIFICATION_HELPERS:
            return True

    for child in ast.iter_child_nodes(node):
        if _node_walks_helper_call(child):
            return True

    return False


# Standard Django HTTP handler method names that form the actual request
# path when ``method_decorator(..., name='dispatch')`` is used.
_HTTP_HANDLER_NAMES: frozenset[str] = frozenset(
    {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "head",
        "options",
        "trace",
    }
)


def _extract_method_decorator_name(decorator: ast.AST) -> str | None:
    """
    Extract the ``name=`` argument from a ``@method_decorator(...)`` call.

    Returns the method-name string if the decorator is a ``Call`` with a
    ``name`` keyword whose value is a string literal; returns ``None``
    otherwise (including when *decorator* is not a ``Call`` at all).
    """
    if not isinstance(decorator, ast.Call):
        return None
    for kw in decorator.keywords:
        if (
            kw.arg == "name"
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
            return kw.value.value
    return None


# ---------------------------------------------------------------------------
# Control-flow predicates
# ---------------------------------------------------------------------------


def _is_constant_true(node: ast.expr) -> bool:
    """
    Return ``True`` if *node* is a compile-time constant-true expression.

    Handles ``True``, non-zero integers (``1``, ``2``, etc.), and non-empty
    strings.  This is intentionally conservative — only obvious literal
    constants are recognised.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, bool) and node.value:
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and node.value != 0:
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value != "":
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, bytes) and node.value != b"":
        return True
    return False


def _is_constant_false(node: ast.expr) -> bool:
    """
    Return ``True`` if *node* is a compile-time constant-false expression.

    Handles ``False``, ``0``, ``0.0``, ``None``, and empty strings.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, bool) and not node.value:
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and node.value == 0:
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, float) and node.value == 0.0:
        return True
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == "":
        return True
    return False


def _has_reachable_helper_in_body(body: list[ast.stmt]) -> bool:
    """
    Return ``True`` if *body* contains a reachable call to an approved helper.

    Conservative control-flow analysis that skips clearly unreachable code:

    * After an unconditional ``return`` or ``raise`` at the current nesting
      level, subsequent sibling statements are treated as unreachable.
    * The body of ``if False:`` / ``if 0:`` (constant-false condition) is
      treated as unreachable; the ``else`` / ``elif`` branch is still checked.
    * The body of ``if True:`` / ``if 1:`` (constant-true condition) is
      treated as reachable; the ``else`` branch is skipped.
    * Non-constant ``if`` conditions have both branches scanned as reachable
      (fails open for uncertainty).
    * ``try`` / ``with`` / ``for`` / ``while`` compound statements are
      scanned at the surface level via ``_node_walks_helper_call``.

    Does **not** descend into nested ``FunctionDef``, ``AsyncFunctionDef``,
    ``ClassDef``, or ``Lambda`` boundaries — that is delegated to
    ``_node_walks_helper_call``.
    """
    for stmt in body:
        # --- ``if`` statements: special reachability handling ---------------
        if isinstance(stmt, ast.If):
            if _is_constant_false(stmt.test):
                # Body is unreachable; check orelse (elif/else) only
                if stmt.orelse and _has_reachable_helper_in_body(stmt.orelse):
                    return True
            elif _is_constant_true(stmt.test):
                # Body is definitely reachable; else branch is unreachable
                if _has_reachable_helper_in_body(stmt.body):
                    return True
            else:
                # Non-constant condition: scan both branches conservatively
                if _has_reachable_helper_in_body(stmt.body):
                    return True
                if stmt.orelse and _has_reachable_helper_in_body(stmt.orelse):
                    return True
            continue

        # --- Other statement types -----------------------------------------
        if _node_walks_helper_call(stmt):
            return True

        # Unconditional exit — subsequent siblings are unreachable
        if isinstance(stmt, (ast.Return, ast.Raise)):
            return False

    return False


def _extract_http_method_names(body: list[ast.stmt]) -> set[str] | None:
    """
    Extract ``http_method_names`` from a class body, or ``None`` if unset.

    Returns the set of allowed HTTP method names when the attribute is
    assigned as a list of string literals.  Returns ``None`` when the
    attribute is not found (meaning all standard Django HTTP handlers are
    allowed by default).
    """
    for stmt in body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "http_method_names":
                    if isinstance(stmt.value, ast.List):
                        methods: set[str] = set()
                        for elt in stmt.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                methods.add(elt.value)
                        return methods
    return None


# ---------------------------------------------------------------------------
# AST visitor
# ---------------------------------------------------------------------------


class _CsrfExemptVisitor(ast.NodeVisitor):
    """Collect ``csrf_exempt`` scopes that lack an approved verification call."""

    def __init__(self) -> None:
        super().__init__()
        # List of (lineno, description) for each uncovered csrf_exempt scope
        self.violations: list[tuple[int, str]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check standalone function definitions."""
        self._check_csrf_exempt_scope(node, node.decorator_list, node.body)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Check async function definitions."""
        self._check_csrf_exempt_scope(node, node.decorator_list, node.body)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """
        Check class definitions with a csrf_exempt decorator.

        For classes (typically ``@method_decorator(csrf_exempt, name='dispatch')``),
        we search **only the named method and standard HTTP handler methods** for
        a helper call — arbitrary sibling helpers (e.g. ``_parse_payload``,
        ``_validate``) are excluded so that unrelated code cannot satisfy the
        pairing requirement.
        """
        if not any(_is_csrf_exempt_decorator(d) for d in node.decorator_list):
            self.generic_visit(node)
            return

        # Determine which methods to inspect based on the decorator's ``name=``.
        method_names_to_check: set[str] = set()
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Name)
                and decorator.func.id == METHOD_DECORATOR_NAME
            ):
                name_val = _extract_method_decorator_name(decorator)
                if name_val is not None:
                    method_names_to_check.add(name_val)

        # Add standard HTTP handler methods that are allowed by
        # ``http_method_names`` (if defined on the class).  These form the
        # actual request path when ``method_decorator`` targets ``dispatch``.
        allowed_http_methods = _extract_http_method_names(node.body)
        if allowed_http_methods is not None:
            for handler in _HTTP_HANDLER_NAMES:
                if handler in allowed_http_methods:
                    method_names_to_check.add(handler)
        else:
            # No explicit restriction — all standard handlers are allowed
            method_names_to_check.update(_HTTP_HANDLER_NAMES)

        helper_found = False
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name in method_names_to_check and _has_reachable_helper_in_body(item.body):
                    helper_found = True
                    break

        if not helper_found:
            helpers_display = "/".join(sorted(APPROVED_VERIFICATION_HELPERS))
            self.violations.append(
                (
                    node.lineno,
                    f"class {node.name} applies csrf_exempt without calling an "
                    f"approved verification helper ({helpers_display})",
                )
            )

        self.generic_visit(node)

    def _check_csrf_exempt_scope(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        decorator_list: list[ast.expr],
        body: list[ast.stmt],
    ) -> None:
        if not any(_is_csrf_exempt_decorator(d) for d in decorator_list):
            return

        if not _has_reachable_helper_in_body(body):
            helpers_display = "/".join(sorted(APPROVED_VERIFICATION_HELPERS))
            self.violations.append(
                (
                    node.lineno,
                    f"function {node.name} applies csrf_exempt without calling an "
                    f"approved verification helper ({helpers_display})",
                )
            )


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def _check_module_source(source_dir: Path) -> dict[Path, list[tuple[int, str]]]:
    """
    Scan *source_dir* for unprotected ``csrf_exempt`` callsites.

    Returns a mapping from file path to list of ``(lineno, description)``
    tuples for every uncovered call found.
    """
    results: dict[Path, list[tuple[int, str]]] = {}
    for py_file in sorted(source_dir.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            # Skip files with syntax errors (unlikely in a healthy repo)
            continue
        visitor = _CsrfExemptVisitor()
        visitor.visit(tree)
        if visitor.violations:
            results[py_file] = visitor.violations
    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run the csrf_exempt gate; exit 0 on clean, 1 on violations, 2 on error."""
    if argv is None:
        argv = sys.argv[1:]

    repo_root = _DEFAULT_REPO_ROOT
    if argv:
        repo_root = Path(argv[0]).resolve()

    modules_root = (repo_root / MODULES_DIR_RELATIVE).resolve()

    if not modules_root.is_dir():
        print(f"ERROR: Modules directory not found: {modules_root}", file=sys.stderr)
        return 2

    all_violations: list[tuple[str, Path, int, str]] = []

    # ---- Scan quickscale_modules/*/src/ -----------------------------------
    for mod_dir in sorted(modules_root.iterdir()):
        if not mod_dir.is_dir():
            continue

        mod_name = mod_dir.name

        if mod_name in EXEMPT_MODULES:
            continue

        src_dir = mod_dir / "src"
        if not src_dir.is_dir():
            continue

        violations_by_file = _check_module_source(src_dir)

        if not violations_by_file:
            continue

        header_printed = False
        for py_file, violations in sorted(violations_by_file.items()):
            rel_path = py_file.relative_to(src_dir)
            for lineno, description in violations:
                if not header_printed:
                    print(f"[{mod_name}] Unprotected csrf_exempt usage:")
                    header_printed = True
                print(f"  {rel_path}:{lineno}  {description}")
                all_violations.append((mod_name, rel_path, lineno, description))

    total = len(all_violations)
    if total == 0:
        print(
            "No unprotected csrf_exempt usage found — "
            "all csrf_exempt-annotated scopes pair with an approved "
            "verification helper."
        )
    else:
        helpers_display = ", ".join(sorted(APPROVED_VERIFICATION_HELPERS))
        print(
            f"\n❌ {total} unprotected csrf_exempt usage(s) found "
            f"(hard-fail after SA46).\n"
            f"Every csrf_exempt callsite must call one of:\n"
            f"    {helpers_display}\n"
        )

    # Hard-fail: exit 1 when violations exist, 0 on clean
    return 1 if total > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
