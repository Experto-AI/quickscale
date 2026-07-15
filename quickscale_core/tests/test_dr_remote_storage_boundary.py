"""Closed-schema AST boundary gate for ``quickscale_core._dr_remote_storage``.

SA89b Phase 1: this module is a self-contained AST scanner that enforces the
closed-schema contract of ``quickscale_core/_dr_remote_storage.py``.

**Rules enforced**

1. Zero imports from ``quickscale_modules``, ``models``, or ``django.db``.
2. Zero ``.objects`` attribute access (Django manager guard).
3. Exactly one ``storage.save()`` call in ``upload_file_to_s3``.
4. Exactly one ``storage.delete()`` call in ``delete_s3_key``.
5. No ORM-like method calls (``.refresh_from_db()``, ``.filter()``, etc.).
6. No classes defined at module level.
7. No ``__all__`` export list.
8. Exact function signatures (name, parameters, return annotation).
9. No dynamic imports (``__import__``, ``importlib``).
10. No re-exports of ``S3Storage`` or ``File`` at module level.
"""

from __future__ import annotations

import ast
import pathlib


# ---------------------------------------------------------------------------
# Target file
# ---------------------------------------------------------------------------

_TARGET = (
    pathlib.Path(__file__).resolve().parent.parent
    / "src"
    / "quickscale_core"
    / "_dr_remote_storage.py"
)

_FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "quickscale_modules",
        "models",
        "django.db",
    }
)

# Only these storage method calls are legitimate (on a proven S3Storage)
_ALLOWED_METHODS = frozenset({"save", "delete"})
_ALWAYS_FORBIDDEN = frozenset(
    {
        "refresh_from_db",
        "filter",
        "get",
        "create",
        "update",
        "bulk_create",
        "bulk_update",
    }
)

# Expected signatures: (param_names, return_annotation)
_EXPECTED_SIGNATURES: dict[str, tuple[list[str], str]] = {
    "upload_file_to_s3": (
        ["local_path", "requested_key", "storage_options"],
        "str",
    ),
    "delete_s3_key": (
        ["requested_key", "storage_options"],
        "None",
    ),
}


# ---------------------------------------------------------------------------
# AST scanners
# ---------------------------------------------------------------------------


def _read_target() -> tuple[pathlib.Path, ast.AST]:
    """Read and parse the target file."""
    source = _TARGET.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_TARGET))
    return _TARGET, tree


def _scan_forbidden_imports(tree: ast.AST) -> list[str]:
    """Return diagnostics for imports from forbidden roots."""
    diags: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for root in _FORBIDDEN_IMPORT_ROOTS:
                    if alias.name.startswith(root):
                        diags.append(
                            f"line {node.lineno}: forbidden import '{alias.name}'"
                        )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for root in _FORBIDDEN_IMPORT_ROOTS:
                    if node.module.startswith(root):
                        diags.append(
                            f"line {node.lineno}: forbidden import from '{node.module}'"
                        )
        # Dynamic imports
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                diags.append(f"line {node.lineno}: dynamic __import__ call")
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "importlib"
                and node.func.attr == "import_module"
            ):
                diags.append(
                    f"line {node.lineno}: dynamic importlib.import_module call"
                )
    return diags


def _scan_objects_access(tree: ast.AST) -> list[str]:
    """Return diagnostics for ``.objects`` attribute access."""
    diags: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "objects":
            diags.append(f"line {node.lineno}: forbidden '.objects' access")
    return diags


def _scan_model_method_calls(
    tree: ast.AST,
    function_name: str | None = None,
) -> list[str]:
    """Return diagnostics for forbidden ORM-like method calls.

    Allowed: exactly one ``storage.save()`` in upload, one ``storage.delete()``
    in delete — proven by a local ``S3Storage`` assignment.
    """
    assert isinstance(tree, ast.Module), "tree must be a parsed Module"
    diags: list[str] = []

    # Find S3Storage import status
    has_s3_import = False
    for node in ast.iter_child_nodes(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "storages.backends.s3"
            and any(alias.name == "S3Storage" for alias in node.names)
        ):
            has_s3_import = True
            break

    # Sentinel for function/class scope boundaries — do not traverse into
    # these with ast.walk since the recursive _walk handles them separately.
    _SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    def _pruning_ast_walk(node: ast.AST) -> list[ast.AST]:
        """Yield all descendant AST nodes, pruning at nested lexical scope
        boundaries (FunctionDef, AsyncFunctionDef, ClassDef, Lambda).

        Unlike ``ast.walk``, this does NOT descend into the bodies of nested
        function, async-function, class, or lambda definitions.
        """
        _BOUNDARY = (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
            ast.Lambda,
        )
        result: list[ast.AST] = []
        stack = [node]
        while stack:
            current = stack.pop()
            result.append(current)
            if isinstance(current, _BOUNDARY):
                continue
            stack.extend(reversed(list(ast.iter_child_nodes(current))))
        return result

    def _walk(
        stmts: list[ast.stmt],
        proven: set[str],
        s3_avail: bool,
        save_count: list[int],
        delete_count: list[int],
    ) -> None:
        for stmt in stmts:
            # --- Scope boundaries first (skip expression scan) ---
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_import = False
                for child in stmt.body:
                    if (
                        isinstance(child, ast.ImportFrom)
                        and child.module == "storages.backends.s3"
                        and any(alias.name == "S3Storage" for alias in child.names)
                    ):
                        local_import = True
                        break
                _walk(
                    stmt.body,
                    set(),
                    s3_avail or local_import,
                    save_count,
                    delete_count,
                )
                continue  # skip expression scan — handled recursively

            if isinstance(stmt, ast.ClassDef):
                continue  # classes not allowed — handled by class scanner

            # --- Track S3Storage assignment ---
            if isinstance(stmt, ast.Assign):
                is_s3 = (
                    s3_avail
                    and isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.func, ast.Name)
                    and stmt.value.func.id == "S3Storage"
                )
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        if is_s3:
                            proven.add(target.id)
                        elif target.id in proven:
                            proven.discard(target.id)

            # --- Check calls (scope boundaries already pruned) ---
            for node in _pruning_ast_walk(stmt):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute):
                    continue

                if func.attr in _ALWAYS_FORBIDDEN:
                    diags.append(f"line {node.lineno}: forbidden '.{func.attr}()' call")
                    continue

                if func.attr not in _ALLOWED_METHODS:
                    continue

                # Check if receiver is a simple proven name
                receiver = func.value
                if isinstance(receiver, ast.Name) and receiver.id in proven:
                    if func.attr == "save":
                        save_count[0] += 1
                    elif func.attr == "delete":
                        delete_count[0] += 1
                else:
                    diags.append(f"line {node.lineno}: unproven '.{func.attr}()' call")

    def _walk_direct_scope(
        stmts: list[ast.stmt],
        proven: set[str],
        s3_avail: bool,
        save_count: list[int],
        delete_count: list[int],
    ) -> None:
        """Walk statements counting save/delete calls, stopping at nested
        function/class/lambda scope boundaries (each is counted separately).
        """
        _SCOPE_BOUNDARY = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

        for stmt in stmts:
            # Scope boundaries — skip entirely
            if isinstance(stmt, _SCOPE_BOUNDARY):
                continue

            # --- Track S3Storage assignment ---
            if isinstance(stmt, ast.Assign):
                is_s3 = (
                    s3_avail
                    and isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.func, ast.Name)
                    and stmt.value.func.id == "S3Storage"
                )
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        if is_s3:
                            proven.add(target.id)
                        elif target.id in proven:
                            proven.discard(target.id)

            # --- Check calls (scope boundaries already pruned) ---
            for node in _pruning_ast_walk(stmt):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute):
                    continue

                if func.attr in _ALWAYS_FORBIDDEN:
                    diags.append(f"line {node.lineno}: forbidden '.{func.attr}()' call")
                    continue

                if func.attr not in _ALLOWED_METHODS:
                    continue

                receiver = func.value
                if isinstance(receiver, ast.Name) and receiver.id in proven:
                    if func.attr == "save":
                        save_count[0] += 1
                    elif func.attr == "delete":
                        delete_count[0] += 1
                else:
                    diags.append(f"line {node.lineno}: unproven '.{func.attr}()' call")

    save_count: list[int] = [0]
    delete_count: list[int] = [0]
    _walk(tree.body, set(), has_s3_import, save_count, delete_count)

    # Module-wide totals — exactly one save, one delete
    if save_count[0] != 1:
        diags.append(
            f"module: expected exactly 1 storage.save() call across the "
            f"entire module, found {save_count[0]}"
        )
    if delete_count[0] != 1:
        diags.append(
            f"module: expected exactly 1 storage.delete() call across the "
            f"entire module, found {delete_count[0]}"
        )

    # Per-function call counts and exclusivity — true lexical scope.
    # Each function (including nested) is checked in isolation: nested
    # function/class/lambda bodies do NOT contribute to the parent scope's
    # counts.
    def _collect_all_lexical_scopes(
        node: ast.AST,
    ) -> list[tuple[str | None, ast.AST, int]]:
        """Recursively collect all lexical scope definitions
        (FunctionDef, AsyncFunctionDef, ClassDef, Lambda) even through
        intervening control-flow nodes.

        Returns list of (name, node, lineno) tuples; lambdas have name=None.
        """
        scopes: list[tuple[str | None, ast.AST, int]] = []
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append((child.name, child, child.lineno))
                scopes.extend(_collect_all_lexical_scopes(child))
            elif isinstance(child, ast.ClassDef):
                scopes.append((child.name, child, child.lineno))
                scopes.extend(_collect_all_lexical_scopes(child))
            elif isinstance(child, ast.Lambda):
                scopes.append((None, child, child.lineno))
            else:
                scopes.extend(_collect_all_lexical_scopes(child))
        return scopes

    for scope_name, scope_node, scope_lineno in _collect_all_lexical_scopes(tree):
        f_has_s3 = has_s3_import or _scope_has_local_s3_import(scope_node)
        f_save: list[int] = [0]
        f_delete: list[int] = [0]

        if isinstance(
            scope_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            _walk_direct_scope(scope_node.body, set(), f_has_s3, f_save, f_delete)
        elif isinstance(scope_node, ast.Lambda):
            _count_lambda_calls(scope_node, f_save, f_delete)

        # Determine display name for diagnostics
        if isinstance(scope_node, ast.Lambda):
            display_name = f"lambda at line {scope_lineno}"
        else:
            display_name = scope_name  # type: ignore[assignment]

        if display_name == "upload_file_to_s3":
            if f_save[0] != 1:
                diags.append(
                    f"line {scope_lineno}: 'upload_file_to_s3' must contain "
                    f"exactly 1 storage.save() call, found {f_save[0]}"
                )
            if f_delete[0] != 0:
                diags.append(
                    f"line {scope_lineno}: 'upload_file_to_s3' must contain "
                    f"exactly 0 storage.delete() calls, found {f_delete[0]}"
                )
        elif display_name == "delete_s3_key":
            if f_delete[0] != 1:
                diags.append(
                    f"line {scope_lineno}: 'delete_s3_key' must contain "
                    f"exactly 1 storage.delete() call, found {f_delete[0]}"
                )
            if f_save[0] != 0:
                diags.append(
                    f"line {scope_lineno}: 'delete_s3_key' must contain "
                    f"exactly 0 storage.save() calls, found {f_save[0]}"
                )
        else:
            if f_save[0] != 0 or f_delete[0] != 0:
                diags.append(
                    f"line {scope_lineno}: '{display_name}' must not contain any "
                    f"storage.save() or storage.delete() calls, "
                    f"found save={f_save[0]}, delete={f_delete[0]}"
                )

    return diags


def _scope_has_local_s3_import(scope_node: ast.AST) -> bool:
    """Return True if *scope_node* body contains an S3Storage import.
    Handles FunctionDef, AsyncFunctionDef, and ClassDef; Lambdas have
    no body statements and always return False.
    """
    body: list[ast.stmt] = getattr(scope_node, "body", [])
    for stmt in body:
        if (
            isinstance(stmt, ast.ImportFrom)
            and stmt.module == "storages.backends.s3"
            and any(alias.name == "S3Storage" for alias in stmt.names)
        ):
            return True
    return False


def _count_lambda_calls(
    lambda_node: ast.Lambda,
    save_count: list[int],
    delete_count: list[int],
) -> None:
    """Count save/delete calls in a lambda body expression.

    Lambdas capture variables by closure, so a Name receiver may refer
    to a proven S3Storage from the enclosing scope. We conservatively
    count any Name-receiver save/delete call — this avoids under-counting
    (false negatives) in the closed-schema contract while keeping the
    analysis independent of parent-scope provenance tracking.
    """
    for node in ast.walk(lambda_node.body):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in _ALLOWED_METHODS:
            continue
        if not isinstance(func.value, ast.Name):
            continue
        if func.attr == "save":
            save_count[0] += 1
        elif func.attr == "delete":
            delete_count[0] += 1


def _scan_class_definitions(tree: ast.AST) -> list[str]:
    """Return diagnostics for any class defined in the module."""
    diags: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            diags.append(
                f"line {node.lineno}: class definition '{node.name}' is forbidden"
            )
    return diags


def _scan_all_export(tree: ast.AST) -> list[str]:
    """Return diagnostic if ``__all__`` is defined in the module."""
    diags: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    diags.append(
                        f"line {node.lineno}: __all__ export is forbidden "
                        f"in a private module"
                    )
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                diags.append(f"line {node.lineno}: __all__ export is forbidden")
    return diags


def _return_annotation_str(returns: ast.expr | None) -> str:
    """Return a string representation of a return annotation.

    Handles ``ast.Name`` (e.g. ``str``), ``ast.Constant`` (e.g. ``None``),
    and ``None`` (missing annotation).
    """
    if returns is None:
        return "<no return annotation>"
    if isinstance(returns, ast.Name):
        return returns.id
    if isinstance(returns, ast.Constant):
        if returns.value is None:
            return "None"
        return repr(returns.value)
    if isinstance(returns, ast.Subscript):
        # e.g. dict[str, Any]
        return "complex"
    return "complex"


def _scan_signatures(tree: ast.AST) -> list[str]:
    """Verify exact function signatures."""
    diags: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name
        if name not in _EXPECTED_SIGNATURES:
            diags.append(f"line {node.lineno}: unexpected function '{name}'")
            continue

        expected_params, expected_return = _EXPECTED_SIGNATURES[name]

        # Check parameter names
        param_names = [
            arg.arg
            for arg in node.args.args
            if arg.arg != "self"  # not a method
        ]
        if param_names != expected_params:
            diags.append(
                f"line {node.lineno}: '{name}' expected params "
                f"{expected_params}, got {param_names}"
            )

        # Check return annotation
        actual_return = _return_annotation_str(node.returns)
        if actual_return != expected_return:
            diags.append(
                f"line {node.lineno}: '{name}' expected return "
                f"'{expected_return}', got '{actual_return}'"
            )

    return diags


def _scan_re_exports(tree: ast.AST) -> list[str]:
    """Verify no module-level re-exports of S3Storage or File."""
    diags: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module in ("storages.backends.s3", "django.core.files"):
                # These are allowed only INSIDE function bodies
                diags.append(
                    f"line {node.lineno}: module-level import from "
                    f"'{node.module}' is forbidden — use function-local imports"
                )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("S3Storage", "File"):
                    diags.append(
                        f"line {node.lineno}: re-export of '{target.id}' is forbidden"
                    )
    return diags


# ---------------------------------------------------------------------------
# Collect all diagnostics
# ---------------------------------------------------------------------------


def _collect_boundary_diagnostics() -> list[str]:
    """Run all boundary scans and return combined diagnostics."""
    target_path, tree = _read_target()
    diags: list[str] = []

    prefix = target_path.relative_to(target_path.parent.parent.parent.parent)

    for diagnostic in _scan_forbidden_imports(tree):
        diags.append(f"{prefix}: {diagnostic}")
    for diagnostic in _scan_objects_access(tree):
        diags.append(f"{prefix}: {diagnostic}")
    for diagnostic in _scan_model_method_calls(tree):
        diags.append(f"{prefix}: {diagnostic}")
    for diagnostic in _scan_class_definitions(tree):
        diags.append(f"{prefix}: {diagnostic}")
    for diagnostic in _scan_all_export(tree):
        diags.append(f"{prefix}: {diagnostic}")
    for diagnostic in _scan_signatures(tree):
        diags.append(f"{prefix}: {diagnostic}")
    for diagnostic in _scan_re_exports(tree):
        diags.append(f"{prefix}: {diagnostic}")

    return diags


# ===================================================================
# Tests
# ===================================================================


class TestDRRemoteStorageBoundary:
    """Closed-schema AST gate for ``quickscale_core._dr_remote_storage``."""

    def test_target_file_exists(self) -> None:
        """The target file exists and is readable."""
        assert _TARGET.exists(), f"Target file not found: {_TARGET}"

    def test_zero_boundary_violations(self) -> None:
        """No forbidden imports, objects, methods, classes, exports, or
        signature mismatches in ``_dr_remote_storage.py``."""
        diags = _collect_boundary_diagnostics()
        assert not diags, f"Found {len(diags)} boundary violation(s):\n" + "\n".join(
            diags
        )

    def test_parse_succeeds(self) -> None:
        """The target file parses without syntax errors."""
        _read_target()  # raises on parse failure


# ===================================================================
# Synthetic negatives — prove each checker fires correctly
# ===================================================================


class TestBoundaryScanner:
    """Synthetic negative tests for the boundary scanner itself."""

    def _run_checks(self, source: str) -> list[str]:
        """Run all boundary scanners on *source* and return diagnostics."""
        tree = ast.parse(source, filename="test.py")
        diags: list[str] = []
        diags.extend(_scan_forbidden_imports(tree))
        diags.extend(_scan_objects_access(tree))
        diags.extend(_scan_model_method_calls(tree))
        diags.extend(_scan_class_definitions(tree))
        diags.extend(_scan_all_export(tree))
        diags.extend(_scan_signatures(tree))
        diags.extend(_scan_re_exports(tree))
        return diags

    # ------------------------------------------------------------------
    # Forbidden import tests
    # ------------------------------------------------------------------

    def test_detects_quickscale_modules_import(self) -> None:
        source = "import quickscale_modules_backups.models"
        diags = self._run_checks(source)
        assert any("forbidden import" in d for d in diags)

    def test_detects_from_quickscale_modules_import(self) -> None:
        source = "from quickscale_modules_backups import models"
        diags = self._run_checks(source)
        assert any("forbidden import" in d for d in diags)

    def test_detects_django_db_import(self) -> None:
        source = "from django.db import models"
        diags = self._run_checks(source)
        assert any("forbidden import" in d for d in diags)

    def test_allows_storages_import(self) -> None:
        source = "def f():\n    from storages.backends.s3 import S3Storage\n"
        diags = self._run_checks(source)
        # Module-level scan should not flag function-local imports
        assert not any("forbidden import" in d for d in diags), str(diags)

    # ------------------------------------------------------------------
    # .objects access
    # ------------------------------------------------------------------

    def test_detects_objects_access(self) -> None:
        source = "artifact.objects.filter()"
        diags = self._run_checks(source)
        assert any(".objects" in d for d in diags)

    # ------------------------------------------------------------------
    # ORM method calls
    # ------------------------------------------------------------------

    def test_detects_refresh_from_db(self) -> None:
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def f():\n"
            "    storage = S3Storage(**options)\n"
            "    storage.refresh_from_db()\n"
        )
        diags = self._run_checks(source)
        assert any("refresh_from_db" in d for d in diags)

    def test_detects_filter_call(self) -> None:
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def f():\n"
            "    storage = S3Storage(**options)\n"
            "    storage.filter(key='x')\n"
        )
        diags = self._run_checks(source)
        assert any(".filter()" in d for d in diags)

    def test_detects_unproven_save(self) -> None:
        source = "def f():\n    artifact.save()\n"
        diags = self._run_checks(source)
        assert any("unproven" in d or ".save()" in d for d in diags)

    # ------------------------------------------------------------------
    # Save/delete call count & exclusivity
    # ------------------------------------------------------------------

    def test_detects_private_helper_with_save(self) -> None:
        """Private helper function with storage.save() is flagged.
        Direct ``_scan_model_method_calls`` call, exact scope substring.
        """
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def _helper():\n"
            "    storage = S3Storage()\n"
            "    storage.save('k', 'f')\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    pass\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    pass\n"
        )
        tree = ast.parse(source, filename="test.py")
        diags = _scan_model_method_calls(tree)
        assert any("_helper" in d and "save=1" in d for d in diags), str(diags)

    def test_detects_wrong_function_with_save(self) -> None:
        """Unexpected function with storage.save() is flagged.
        Direct ``_scan_model_method_calls`` call, exact scope substring.
        """
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def another_upload():\n"
            "    storage = S3Storage()\n"
            "    storage.save('k', 'f')\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    pass\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    pass\n"
        )
        tree = ast.parse(source, filename="test.py")
        diags = _scan_model_method_calls(tree)
        assert any("another_upload" in d and "save=1" in d for d in diags), str(diags)

    def test_detects_duplicate_save_in_upload(self) -> None:
        """Two storage.save() calls in upload_file_to_s3 are flagged."""
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    storage = S3Storage()\n"
            "    storage.save('a', 'f')\n"
            "    storage.save('b', 'f')\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    pass\n"
        )
        diags = self._run_checks(source)
        assert any(
            "upload_file_to_s3" in d and "save" in d and "2" in d for d in diags
        ), str(diags)

    def test_detects_extra_delete_in_upload(self) -> None:
        """storage.delete() call in upload_file_to_s3 is flagged."""
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    storage = S3Storage()\n"
            "    storage.save('k', 'f')\n"
            "    storage.delete('k')\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    pass\n"
        )
        diags = self._run_checks(source)
        assert any("upload_file_to_s3" in d and "delete" in d for d in diags), str(
            diags
        )

    def test_detects_extra_save_in_delete(self) -> None:
        """storage.save() call in delete_s3_key is flagged."""
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    pass\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    storage = S3Storage()\n"
            "    storage.delete('k')\n"
            "    storage.save('k', 'f')\n"
        )
        diags = self._run_checks(source)
        assert any("delete_s3_key" in d and "save" in d for d in diags), str(diags)

    # ------------------------------------------------------------------
    # Nested helper scope isolation
    # ------------------------------------------------------------------

    def test_detects_nested_helper_save_inside_upload(self) -> None:
        """Nested helper with storage.save() in upload_file_to_s3 is
        flagged as its own lexical scope, not attributed to the parent.
        Each function allocates its own proven S3Storage.
        """
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    storage = S3Storage()\n"
            "    def _inner():\n"
            "        s = S3Storage()\n"
            "        s.save('k', 'f')\n"
            "    storage.save('k', django_file)\n"
            "    return requested_key\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    pass\n"
        )
        tree = ast.parse(source, filename="test.py")
        diags = _scan_model_method_calls(tree)
        # _inner scope isolated: its save=1 must be flagged independently
        assert any("_inner" in d and "save=1" in d for d in diags), str(diags)

    def test_detects_nested_helper_delete_inside_delete(self) -> None:
        """Nested helper with storage.delete() in delete_s3_key is
        flagged as its own lexical scope, not attributed to the parent.
        Each function allocates its own proven S3Storage.
        """
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    pass\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    storage = S3Storage(**storage_options)\n"
            "    def _inner():\n"
            "        s = S3Storage()\n"
            "        s.delete('k')\n"
            "    storage.delete('k')\n"
        )
        tree = ast.parse(source, filename="test.py")
        diags = _scan_model_method_calls(tree)
        assert any("_inner" in d and "delete=1" in d for d in diags), str(diags)

    # ------------------------------------------------------------------
    # Lexical-scope pruning regression negatives (SA89B-CR-001)
    # ------------------------------------------------------------------

    def test_nested_function_inside_if_save_not_leaked(self) -> None:
        """Nested function inside ``if`` block: its ``storage.save()`` is
        NOT attributed to the parent's per-function count. Proves the
        pruning visitor genuinely skips nested lexical scopes even when
        they are wrapped in control-flow statements.
        """
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    storage = S3Storage()\n"
            "    if True:\n"
            "        def _inner():\n"
            "            s = S3Storage()\n"
            "            s.save('k', 'f')\n"
            "        storage.save('k', django_file)\n"
            "    return requested_key\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    pass\n"
        )
        tree = ast.parse(source, filename="test.py")
        diags = _scan_model_method_calls(tree)
        # The only diagnostics should be about delete_s3_key having no
        # delete call — the nested function's save inside ``if`` is
        # pruned and NOT leaked into upload_file_to_s3's count.
        assert not any(
            "upload_file_to_s3" in d and "save=" in d and "found" in d for d in diags
        ), str(diags)
        # _inner is now discovered through control-flow traversal and
        # analyzed as its own lexical scope. Its save=1 is reported
        # independently (not attributed to upload_file_to_s3).
        assert any("_inner" in d and "save=1" in d for d in diags), str(diags)

    def test_nested_async_function_inside_if_save_not_leaked(self) -> None:
        """Async function nested inside ``if`` block: its ``storage.save()``
        is NOT leaked into the parent function count.
        """
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    storage = S3Storage()\n"
            "    if True:\n"
            "        async def _inner():\n"
            "            s = S3Storage()\n"
            "            s.save('k', 'f')\n"
            "        storage.save('k', django_file)\n"
            "    return requested_key\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    pass\n"
        )
        tree = ast.parse(source, filename="test.py")
        diags = _scan_model_method_calls(tree)
        assert not any(
            "upload_file_to_s3" in d and "save=" in d and "found" in d for d in diags
        ), str(diags)
        assert any("_inner" in d and "save=1" in d for d in diags), str(diags)

    def test_lambda_save_not_leaked_to_parent(self) -> None:
        """Lambda calling ``storage.save()`` with the outer-proven variable
        must NOT inflate the parent's per-function save count.
        """
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    storage = S3Storage()\n"
            "    on_complete = lambda: storage.save('k', 'f')\n"
            "    storage.save('k', django_file)\n"
            "    return requested_key\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    pass\n"
        )
        tree = ast.parse(source, filename="test.py")
        diags = _scan_model_method_calls(tree)
        # The lambda's .save() must not be attributed to parent,
        # so upload_file_to_s3 should have exactly 1 save.
        assert not any(
            "upload_file_to_s3" in d and "save=" in d and "found" in d for d in diags
        ), str(diags)
        # The lambda is now discovered through control-flow traversal
        # and analyzed as its own lexical scope. Its save=1 is reported
        # independently (not attributed to upload_file_to_s3).
        assert any("lambda" in d and "save=1" in d for d in diags), str(diags)

    def test_class_save_not_leaked_to_parent(self) -> None:
        """Class method calling ``storage.save()`` inside a function
        must NOT inflate the parent function's per-function count.
        """
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    storage = S3Storage()\n"
            "    class Helper:\n"
            "        def save_it(self):\n"
            "            s = S3Storage()\n"
            "            s.save('k', 'f')\n"
            "    storage.save('k', django_file)\n"
            "    return requested_key\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    pass\n"
        )
        tree = ast.parse(source, filename="test.py")
        diags = _scan_model_method_calls(tree)
        # upload_file_to_s3 must have exactly 1 save (not inflated)
        assert not any(
            "upload_file_to_s3" in d and "save=" in d and "found" in d for d in diags
        ), str(diags)
        # save_it is now discovered and analyzed as its own lexical
        # scope. Its save=1 is reported independently.
        assert any("save_it" in d and "save=1" in d for d in diags), str(diags)

    def test_direct_if_save_is_counted(self) -> None:
        """Direct ``storage.save()`` inside an ``if`` block IS counted
        in the parent function. Proves control-flow traversal still
        works — the pruning only removes nested lexical scopes, not
        ordinary control-flow branches."""
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    storage = S3Storage()\n"
            "    if True:\n"
            "        storage.save('k', django_file)\n"
            "    return requested_key\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    pass\n"
        )
        tree = ast.parse(source, filename="test.py")
        diags = _scan_model_method_calls(tree)
        # upload_file_to_s3 must have exactly 1 save (direct, inside if)
        assert not any(
            "upload_file_to_s3" in d and "save=" in d and "found" in d for d in diags
        ), str(diags)

    def test_direct_for_save_is_counted(self) -> None:
        """Direct ``storage.save()`` inside a ``for`` loop IS counted
        in the parent function. Proves for-loop traversal with the
        pruning visitor still works — only nested lexical scopes are
        pruned, not ordinary control-flow bodies."""
        source = (
            "from storages.backends.s3 import S3Storage\n"
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    storage = S3Storage()\n"
            "    for key in [requested_key]:\n"
            "        storage.save(key, django_file)\n"
            "    return requested_key\n"
            "def delete_s3_key(requested_key, storage_options):\n"
            "    pass\n"
        )
        tree = ast.parse(source, filename="test.py")
        diags = _scan_model_method_calls(tree)
        # upload_file_to_s3 must have exactly 1 save (direct, inside for)
        assert not any(
            "upload_file_to_s3" in d and "save=" in d and "found" in d for d in diags
        ), str(diags)

    # ------------------------------------------------------------------
    # Class definitions
    # ------------------------------------------------------------------

    def test_detects_class_definition(self) -> None:
        source = "class MyConfig:\n    pass\n"
        diags = self._run_checks(source)
        assert any("class definition" in d for d in diags)

    # ------------------------------------------------------------------
    # __all__ export
    # ------------------------------------------------------------------

    def test_detects_all_export(self) -> None:
        source = "__all__ = ['upload_file_to_s3']"
        diags = self._run_checks(source)
        assert any("__all__" in d for d in diags)

    def test_detects_annotated_all_export(self) -> None:
        source = "__all__: list[str] = ['upload_file_to_s3']"
        diags = self._run_checks(source)
        assert any("__all__" in d for d in diags)

    # ------------------------------------------------------------------
    # Module-level re-exports
    # ------------------------------------------------------------------

    def test_detects_module_level_s3storage_import(self) -> None:
        source = "from storages.backends.s3 import S3Storage\n"
        diags = self._run_checks(source)
        assert any("module-level import" in d for d in diags)

    def test_detects_module_level_file_import(self) -> None:
        source = "from django.core.files import File\n"
        diags = self._run_checks(source)
        assert any("module-level import" in d for d in diags)

    # ------------------------------------------------------------------
    # Signature validation
    # ------------------------------------------------------------------

    def test_detects_wrong_param_names(self) -> None:
        source = (
            "def upload_file_to_s3(wrong_param: str, other: int) -> str:\n    pass\n"
        )
        tree = ast.parse(source, filename="test.py")
        diags = _scan_signatures(tree)
        assert any("expected params" in d for d in diags)

    def test_detects_missing_return_annotation(self) -> None:
        source = (
            "def upload_file_to_s3(local_path, requested_key, storage_options):\n"
            "    pass\n"
        )
        tree = ast.parse(source, filename="test.py")
        diags = _scan_signatures(tree)
        assert any(
            "expected return" in d and "<no return annotation>" in d for d in diags
        )

    def test_detects_unexpected_function(self) -> None:
        source = "def extra_function():\n    pass\n"
        tree = ast.parse(source, filename="test.py")
        diags = _scan_signatures(tree)
        assert any("unexpected function" in d for d in diags)
