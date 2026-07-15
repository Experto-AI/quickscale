"""Bounded AST regression: zero-edge dependency boundary for dr_engine.

SA89b Phase 1 requires that no executable ``quickscale_modules_backups`` model
import, ``.objects`` call, or direct persisted-record save/refresh/delete exists
in any ``quickscale_core/dr_engine/`` Python source file.

This test scans AST for forbidden patterns and reports file:line diagnostics.
Known exceptions are documented inline.
"""

from __future__ import annotations

import ast
import pathlib


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DR_ENGINE_ROOT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "src"
    / "quickscale_core"
    / "dr_engine"
)

# Files under dr_engine/ to scan (all .py files except __pycache__)
_SCAN_PATTERN = "**/*.py"

# Allowed module-level import targets (Django-free dr_engine sub-modules)
_ALLOWED_IMPORT_ROOTS = frozenset(
    {
        "quickscale_core.dr_engine",
        "quickscale_core.dr_engine.persistence",
        "quickscale_core.dr_engine.primitives",
        "quickscale_core.dr_engine.recovery",
        "quickscale_core.dr_engine.verification",
        "quickscale_core.dr_engine._lock",
        "quickscale_core.dr_engine._paths",
        "quickscale_core.dr_engine._sidecar",
    }
)

# Attribute-access chains that are allowed even though they contain ".objects"
# (non-model storage APIs such as S3Storage, etc.)
_ALLOWED_OBJECTS_ACCESS = frozenset(
    {
        # S3Storage from django-storages has its own .objects attr
        # that is not a Django model manager.
    }
)

# Call patterns that are allowed despite involving model-like methods
# (Non-ORM uses like dict.get, etc.)
_ALLOWED_CALL_PATTERNS: list[str] = []

# SA89b Phase 1 completion: all deferred model imports and .objects accesses
# have been removed from dr_engine.  Empty sets are kept to preserve the
# exception-documentation pattern; any future exception requires explicit
# plan-review approval.
_DEFERRED_IMPORT_EXCEPTIONS: set[tuple[str, str, int]] = {}

_DEFERRED_OBJECTS_EXCEPTIONS: set[tuple[str, str, int]] = {}

# SA89B-CR-001 Phase 2: unconditional, flow-insensitive AST gate.
# Every ``.save()`` / ``.delete()`` / ``.refresh_from_db()`` call in any
# ``dr_engine/`` source file is flagged regardless of receiver, provenance,
# import context, scope, or execution order.  The ``_dr_remote_storage``
# adapter owns the only legitimate S3 save/delete calls — it lives *outside*
# ``dr_engine/`` and is separately gated by ``test_dr_remote_storage_boundary.py``.


# ---------------------------------------------------------------------------
# AST scanning
# ---------------------------------------------------------------------------


def _find_import_context(
    file_path: pathlib.Path,
    tree: ast.AST,
    target_lineno: int,
) -> str | None:
    """Return the function name enclosing *target_lineno*, or None if not inside one."""
    for node in ast.iter_child_nodes(tree):
        # Top-level function
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= target_lineno <= (node.end_lineno or target_lineno):
                return node.name
        # Class
        if isinstance(node, ast.ClassDef):
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if (
                        item.lineno
                        <= target_lineno
                        <= (item.end_lineno or target_lineno)
                    ):
                        return item.name
    return None


def _scan_file_for_forbidden_imports(
    file_path: pathlib.Path,
    tree: ast.AST,
) -> list[str]:
    """Scan one file for imports from quickscale_modules_backups."""
    diagnostics: list[str] = []
    filename = file_path.name

    for node in ast.walk(tree):
        # import quickscale_modules_backups...
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("quickscale_modules_backups"):
                    diag = (
                        f"{file_path.relative_to(DR_ENGINE_ROOT)}:{node.lineno}: "
                        f"forbidden import '{alias.name}'"
                    )
                    diagnostics.append(diag)

        # from quickscale_modules_backups import ...
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("quickscale_modules_backups"):
                func_name = _find_import_context(file_path, tree, node.lineno)
                exception_key = (filename, func_name, node.lineno)
                if exception_key in _DEFERRED_IMPORT_EXCEPTIONS:
                    continue
                diag = (
                    f"{file_path.relative_to(DR_ENGINE_ROOT)}:{node.lineno}: "
                    f"forbidden import from '{node.module}'"
                )
                diagnostics.append(diag)

    return diagnostics


def _scan_file_for_objects_calls(
    file_path: pathlib.Path,
    tree: ast.AST,
) -> list[str]:
    """Scan one file for direct .objects attribute access (model manager)."""
    diagnostics: list[str] = []
    filename = file_path.name

    for node in ast.walk(tree):
        # Look for Attribute access: something.objects.something
        if isinstance(node, ast.Attribute) and node.attr == "objects":
            func_name = _find_import_context(file_path, tree, node.lineno)
            exception_key = (filename, func_name, node.lineno)
            if exception_key in _DEFERRED_OBJECTS_EXCEPTIONS:
                continue
            diag = (
                f"{file_path.relative_to(DR_ENGINE_ROOT)}:{node.lineno}: "
                f"direct '.objects' access detected"
            )
            diagnostics.append(diag)

    return diagnostics


# ---------------------------------------------------------------------------
# Unconditional model-method AST gate
# ---------------------------------------------------------------------------
#
# SA89b Phase 2 replaces the provenance-aware S3Storage analyzer (removed in
# this phase) with a flow-insensitive ``ast.walk`` that flags every
# ``.save()`` / ``.delete()`` / ``.refresh_from_db()`` call unconditionally.
# No receiver/provenance/import/scope/order analysis is performed.

_FORBIDDEN_METHODS: frozenset[str] = frozenset({"save", "delete", "refresh_from_db"})


def _scan_file_for_model_method_calls(
    file_path: pathlib.Path,
    tree: ast.AST,
) -> list[str]:
    """Unconditional, flow-insensitive AST gate for ``dr_engine/``.

    SA89b Phase 2: every ``.save()`` / ``.delete()`` / ``.refresh_from_db()``
    call in any ``dr_engine/`` source file is flagged, regardless of receiver
    type, import context, provenance, scope, or execution order.  The
    ``_dr_remote_storage`` adapter — which lives *outside* ``dr_engine/`` and
    owns the only legitimate S3 save/delete — is separately gated by
    ``test_dr_remote_storage_boundary.py``.

    No receiver/provenance/import/scope/order analysis is performed.  Every
    ``ast.Call`` where ``call.func`` is an ``ast.Attribute`` whose ``attr``
    is one of the forbidden method names is flagged unconditionally.
    """
    diagnostics: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN_METHODS:
                diagnostics.append(
                    f"{file_path.relative_to(DR_ENGINE_ROOT)}:{node.lineno}: "
                    f"direct '.{func.attr}()' call detected",
                )
    return diagnostics


# ---------------------------------------------------------------------------
# Scanner unit-test helpers
# ---------------------------------------------------------------------------


def _scan_source_for_forbidden_imports(
    source: str, filename: str = "test.py"
) -> list[str]:
    """Run the forbidden-imports scanner on *source* and return diagnostics."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return ["<syntax error>"]
    file_path = DR_ENGINE_ROOT / filename
    return _scan_file_for_forbidden_imports(file_path, tree)


def _scan_source_for_objects_calls(source: str, filename: str = "test.py") -> list[str]:
    """Run the objects-call scanner on *source* and return diagnostics."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return ["<syntax error>"]
    file_path = DR_ENGINE_ROOT / filename
    return _scan_file_for_objects_calls(file_path, tree)


def _scan_source_for_model_methods(source: str, filename: str = "test.py") -> list[str]:
    """Run the unconditional model-method gate on *source* and return diagnostics."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return ["<syntax error>"]
    file_path = DR_ENGINE_ROOT / filename
    return _scan_file_for_model_method_calls(file_path, tree)


# ---------------------------------------------------------------------------
# Test: zero forbidden imports
# ---------------------------------------------------------------------------


def _collect_diagnostics() -> list[str]:
    """Collect all dependency-boundary diagnostics across dr_engine."""
    diagnostics: list[str] = []
    for py_file in sorted(DR_ENGINE_ROOT.glob(_SCAN_PATTERN)):
        if py_file.name == "__pycache__":
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            diagnostics.append(
                f"{py_file.relative_to(DR_ENGINE_ROOT)}: syntax error: {exc}"
            )
            continue

        diagnostics.extend(_scan_file_for_forbidden_imports(py_file, tree))
        diagnostics.extend(_scan_file_for_objects_calls(py_file, tree))
        diagnostics.extend(_scan_file_for_model_method_calls(py_file, tree))

    return diagnostics


class TestDependencyBoundary:
    """Zero-edge AST regression for dr_engine dependency boundary."""

    def test_no_forbidden_imports_or_objects(self) -> None:
        """No quickscale_modules_backups imports or .objects calls in dr_engine.

        SA89b Phase 1 completion: all deferred imports and .objects accesses
        have been removed; the persistence provider contract replaces every
        ORM edge, and every dr_engine Python file has zero imports beginning
        ``quickscale_modules_backups``.
        """
        diagnostics = _collect_diagnostics()
        assert not diagnostics, (
            f"Found {len(diagnostics)} dependency-boundary violation(s):\n"
            + "\n".join(diagnostics)
        )

    def test_scan_covers_all_dr_engine_files(self) -> None:
        """Verify that the scan glob covers the expected set of files."""
        scanned = set(
            py.relative_to(DR_ENGINE_ROOT)
            for py in DR_ENGINE_ROOT.glob(_SCAN_PATTERN)
            if py.name != "__pycache__"
        )
        assert scanned, "No files scanned - check DR_ENGINE_ROOT path"
        # At minimum these should exist
        expected_slugs = {
            "__init__.py",
            "adapter.py",
            "orchestration.py",
            "persistence.py",
            "primitives.py",
            "recovery.py",
            "verification.py",
            "_lock.py",
            "_paths.py",
            "_sidecar.py",
        }
        scanned_slugs = {p.name for p in scanned}
        missing = expected_slugs - scanned_slugs
        assert not missing, f"Expected files not found by scanner: {missing}"


class TestModelMethodScanner:
    """Direct scanner tests for the unconditional AST gate.

    SA89b Phase 2 replaces the provenance-aware S3Storage analyzer with an
    unconditional, flow-insensitive ``ast.walk`` that flags every
    ``.save()`` / ``.delete()`` / ``.refresh_from_db()`` call regardless of
    receiver, import context, scope, or execution order.

    Every proof below asserts that the unconditional gate fires (positive
    detection) or does not fire (clean control) as expected.
    """

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _scan(source: str) -> list[str]:
        """Run the unconditional model-method gate on *source*."""
        return _scan_source_for_model_methods(source)

    # ------------------------------------------------------------------
    # Basic detection — each forbidden method on a bare receiver
    # ------------------------------------------------------------------

    def test_detects_bare_save(self) -> None:
        """artifact.save() on a bare name is detected."""
        source = """
def f():
    artifact.save()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_bare_delete(self) -> None:
        """artifact.delete() on a bare name is detected."""
        source = """
def f():
    artifact.delete()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".delete()" in diags[0]

    def test_detects_bare_refresh_from_db(self) -> None:
        """artifact.refresh_from_db() on a bare name is detected."""
        source = """
def f():
    artifact.refresh_from_db()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".refresh_from_db()" in diags[0]

    # ------------------------------------------------------------------
    # S3Storage always detected — no provenance exemption
    # ------------------------------------------------------------------

    def test_detects_s3storage_save(self) -> None:
        """storage.save() on proven S3Storage is still detected (no provenance)."""
        source = """
from storages.backends.s3 import S3Storage
def f():
    storage = S3Storage(**options)
    storage.save(remote_key)
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_s3storage_delete(self) -> None:
        """storage.delete() on proven S3Storage is still detected."""
        source = """
from storages.backends.s3 import S3Storage
def f():
    storage = S3Storage(**options)
    storage.delete(remote_key)
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".delete()" in diags[0]

    def test_detects_s3storage_refresh_from_db(self) -> None:
        """storage.refresh_from_db() on proven S3Storage is detected."""
        source = """
from storages.backends.s3 import S3Storage
def f():
    storage = S3Storage(**options)
    storage.refresh_from_db()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".refresh_from_db()" in diags[0]

    # ------------------------------------------------------------------
    # Descendant / call chains
    # ------------------------------------------------------------------

    def test_detects_descendant_chain_save(self) -> None:
        """storage.artifact.save() — descendant chain is detected."""
        source = """
def f():
    storage.artifact.save()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_call_chain_receiver(self) -> None:
        """obj().save() — call-chain receiver is detected."""
        source = """
def f():
    obj().save()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    # ------------------------------------------------------------------
    # Assign / AnnAssign / AugAssign RHS
    # ------------------------------------------------------------------

    def test_detects_save_in_assign_rhs(self) -> None:
        """x = obj.save() — save on RHS is detected."""
        source = """
def f():
    x = obj.save()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_save_in_annassign_rhs(self) -> None:
        """x: int = obj.save() — save in annotated RHS is detected."""
        source = """
def f():
    x: int = obj.save()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_save_in_augassign_rhs(self) -> None:
        """x += obj.save() — save in augmented RHS is detected."""
        source = """
def f():
    x += obj.save()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    # ------------------------------------------------------------------
    # Decorators / defaults / class bases / keywords
    # ------------------------------------------------------------------

    def test_detects_save_in_decorator(self) -> None:
        """@decorator(obj.save()) — save inside decorator argument is detected."""
        source = """
@decorator(obj.save())
def f():
    pass
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_save_in_default(self) -> None:
        """def f(x=obj.save()) — save in default arg is detected."""
        source = """
def f(x=obj.save()):
    pass
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_save_in_keyword(self) -> None:
        """func(arg=obj.save()) — save in keyword argument is detected."""
        source = """
def f():
    func(arg=obj.save())
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_delete_in_class_base(self) -> None:
        """class C(obj.delete()): — delete in class base expression is detected."""
        source = """
class C(obj.delete()):
    pass
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".delete()" in diags[0]

    # ------------------------------------------------------------------
    # If condition
    # ------------------------------------------------------------------

    def test_detects_save_in_if_condition(self) -> None:
        """if obj.save(): — save in if condition is detected."""
        source = """
def f():
    if obj.save():
        pass
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    # ------------------------------------------------------------------
    # Loop iter / target / body / else / repeated shape
    # ------------------------------------------------------------------

    def test_detects_save_in_for_iter(self) -> None:
        """for x in obj.save(): — save in for iter is detected."""
        source = """
def f():
    for x in obj.save():
        pass
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_save_in_for_else(self) -> None:
        """for ... else: obj.save() — save in loop else is detected."""
        source = """
def f():
    for x in items:
        pass
    else:
        obj.save()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_save_in_while_test(self) -> None:
        """while obj.save(): — save in while test is detected."""
        source = """
def f():
    while obj.save():
        pass
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    # ------------------------------------------------------------------
    # Try body / handler type / handler body / else / finally
    # ------------------------------------------------------------------

    def test_detects_save_in_try_body(self) -> None:
        """obj.save() in try body is detected."""
        source = """
def f():
    try:
        obj.save()
    except Exception:
        pass
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_save_in_except_handler(self) -> None:
        """obj.save() in except handler body is detected."""
        source = """
def f():
    try:
        pass
    except Exception:
        obj.save()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_save_in_except_handler_type(self) -> None:
        """except obj.save(): — save in handler type expression is detected."""
        source = """
def f():
    try:
        pass
    except obj.save():
        pass
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_save_in_try_else(self) -> None:
        """obj.save() in try/else is detected."""
        source = """
def f():
    try:
        pass
    except Exception:
        pass
    else:
        obj.save()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    def test_detects_save_in_try_finally(self) -> None:
        """obj.save() in try/finally is detected."""
        source = """
def f():
    try:
        pass
    finally:
        obj.save()
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    # ------------------------------------------------------------------
    # Cross-function collision (each flagged independently)
    # ------------------------------------------------------------------

    def test_detects_save_in_multiple_functions(self) -> None:
        """save() in two functions produces two diagnostics (no cross-function leak)."""
        source = """
def a():
    artifact.save()

def b():
    thing.save()
"""
        diags = self._scan(source)
        assert len(diags) == 2, f"Expected 2 diagnostics, got {len(diags)}"

    # ------------------------------------------------------------------
    # Use-before-proof / reassignment / delete (all flagged)
    # ------------------------------------------------------------------

    def test_detects_save_before_assign(self) -> None:
        """use before assign is still detected."""
        source = """
def f():
    storage.save(key)
    storage = something
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"

    def test_detects_save_after_reassignment(self) -> None:
        """save after reassignment is still detected."""
        source = """
def f():
    storage = "not a storage"
    storage.save(key)
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"

    def test_detects_save_after_delete(self) -> None:
        """save after delete is still detected."""
        source = """
def f():
    storage = something
    del storage
    storage.save(key)
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"

    # ------------------------------------------------------------------
    # Nested NamedExpr (walrus operator)
    # ------------------------------------------------------------------

    def test_detects_save_in_named_expr(self) -> None:
        """(x := obj.save()) — save in walrus is detected."""
        source = """
def f():
    if (x := obj.save()):
        pass
"""
        diags = self._scan(source)
        assert len(diags) == 1, f"Expected 1 diagnostic, got {len(diags)}"
        assert ".save()" in diags[0]

    # ------------------------------------------------------------------
    # Clean controls: root-private adapter verbs / current dr_engine API
    # (module-level function calls like persistence.save_artifact() are
    # NOT ``.save()`` attribute calls, so the gate does not fire.)
    # ------------------------------------------------------------------

    def test_allows_persistence_save_artifact(self) -> None:
        """persistence.save_artifact(...) is NOT a forbidden method call."""
        source = """
from quickscale_core.dr_engine.persistence import save_artifact
def f():
    save_artifact(artifact, ["status"])
"""
        diags = self._scan(source)
        assert len(diags) == 0, f"Expected 0 diagnostics, got {diags}"

    def test_allows_adapter_capture_snapshot(self) -> None:
        """adapter.capture_snapshot(...) is NOT a forbidden method call."""
        source = """
from quickscale_core.dr_engine.adapter import capture_snapshot
def f():
    capture_snapshot(trigger="manual")
"""
        diags = self._scan(source)
        assert len(diags) == 0, f"Expected 0 diagnostics, got {diags}"

    def test_allows_persistence_get_backup_artifact(self) -> None:
        """persistence.get_backup_artifact(...) is NOT a forbidden method call."""
        source = """
from quickscale_core.dr_engine.persistence import get_backup_artifact
def f():
    artifact = get_backup_artifact(42)
"""
        diags = self._scan(source)
        assert len(diags) == 0, f"Expected 0 diagnostics, got {diags}"

    # ------------------------------------------------------------------
    # Syntax-error fail-closed
    # ------------------------------------------------------------------

    def test_syntax_error_closes_fail(self) -> None:
        """A syntax error returns [\"<syntax error>\"]."""
        diags = self._scan("def broken(")
        assert diags == ["<syntax error>"]
