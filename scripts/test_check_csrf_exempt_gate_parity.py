"""
Parity controls for the SA267(c) ``check_csrf_exempt_gate`` refactor.

The module keeps its pre-split surface; the literal-truthiness fold was
decomposed into private helpers without moving any name.  These controls pin
the preserved surface, the callable homes and signatures, the exact
truthiness verdicts captured from the pre-split fold, and the gate's exact
findings output, so a later slice cannot silently drop, relocate, or reword
them.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

import check_csrf_exempt_gate as gate
import pytest

#: Every pre-split name consumers reach through the module.  The refactor must
#: keep every one of them.
FROZEN_SURFACE = (
    "APPROVED_VERIFICATION_HELPERS",
    "CSRF_EXEMPT_DECORATOR_NAMES",
    "EXEMPT_MODULES",
    "METHOD_DECORATOR_NAME",
    "MODULES_DIR_RELATIVE",
    "Path",
    "REPO_ROOT_ENV",
    "_CsrfExemptVisitor",
    "_HTTP_HANDLER_NAMES",
    "_body_always_exits",
    "_body_contains_helper_call",
    "_check_module_source",
    "_extract_http_method_names",
    "_extract_method_decorator_name",
    "_has_reachable_helper_in_body",
    "_is_csrf_exempt_decorator",
    "_literal_truthiness",
    "_node_walks_helper_call",
    "ast",
    "main",
    "os",
    "sys",
)

#: Every pre-split callable; the in-place refactor moves none of them.
FROZEN_CALLABLE_SURFACE = (
    "_CsrfExemptVisitor",
    "_body_always_exits",
    "_body_contains_helper_call",
    "_check_module_source",
    "_extract_http_method_names",
    "_extract_method_decorator_name",
    "_has_reachable_helper_in_body",
    "_is_csrf_exempt_decorator",
    "_literal_truthiness",
    "_node_walks_helper_call",
    "main",
)

#: The pre-split signature of every callable consumers invoke.
FROZEN_SIGNATURES = {
    "_is_csrf_exempt_decorator": "(decorator: 'ast.expr') -> 'bool'",
    "_body_contains_helper_call": "(body: 'list[ast.stmt]') -> 'bool'",
    "_node_walks_helper_call": "(node: 'ast.AST') -> 'bool'",
    "_extract_method_decorator_name": "(decorator: 'ast.AST') -> 'str | None'",
    "_literal_truthiness": "(node: 'ast.expr') -> 'bool | None'",
    "_body_always_exits": "(body: 'list[ast.stmt]') -> 'bool'",
    "_has_reachable_helper_in_body": "(body: 'list[ast.stmt]') -> 'bool'",
    "_extract_http_method_names": "(body: 'list[ast.stmt]') -> 'set[str] | None'",
    "_check_module_source": "(source_dir: 'Path') -> 'dict[Path, list[tuple[int, str]]]'",
    "main": "(argv: 'list[str] | None' = None) -> 'int'",
}

#: ``(expression source, verdict)`` captured from the pre-split fold.  The
#: corpus covers every documented fold family, the unpack-uncertainty
#: conservatism (CR-SA46-REV-UNPACK-001), and non-constant expressions.
TRUTHINESS_CASES = (
    ("True", True),
    ("False", False),
    ("1", True),
    ("0", False),
    ("-1", True),
    ("-0", False),
    ("+0.0", False),
    ("-1j", True),
    ("0j", False),
    ("None", False),
    ("...", True),
    ("'x'", True),
    ("''", False),
    ("b'x'", True),
    ("b''", False),
    ("()", False),
    ("(1,)", True),
    ("[]", False),
    ("[1]", True),
    ("{}", False),
    ("{'a': 1}", True),
    ("{1}", True),
    ("[*x]", None),
    ("(*x,)", None),
    ("{*x}", None),
    ("{**x}", None),
    ("[1, *x]", True),
    ("(1, *x)", True),
    ("{1, *x}", True),
    ("{'k': 1, **x}", True),
    ("not True", False),
    ("not 0", True),
    ("not 'x'", False),
    ("not x", None),
    ("~0", True),
    ("~1", True),
    ("~False", True),
    ("~True", True),
    ("~-1", None),
    ("+True", True),
    ("-True", True),
    ("-False", False),
    ("x", None),
    ("x + 1", None),
    ("f()", None),
)

CLEAN_OUTPUT = (
    "No unprotected csrf_exempt usage found — "
    "all csrf_exempt-annotated scopes pair with an approved "
    "verification helper.\n"
)

VIOLATING_SOURCE = (
    "from django.views.decorators.csrf import csrf_exempt\n"
    "\n"
    "\n"
    "@csrf_exempt\n"
    "def get(request):\n"
    "    return None\n"
)


def _normalized_signature(function: Callable[..., Any]) -> str:
    return str(inspect.signature(function))


def test_module_surface_is_preserved() -> None:
    """Every pre-split name stays reachable on the module."""
    missing = [name for name in FROZEN_SURFACE if not hasattr(gate, name)]
    assert missing == []


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each callable consumers invoke keeps its pre-split signature."""
    observed = {name: _normalized_signature(getattr(gate, name)) for name in FROZEN_SIGNATURES}
    assert observed == FROZEN_SIGNATURES


def test_pre_split_callables_stay_in_the_module() -> None:
    """The in-place refactor relocates no callable to another module."""
    observed = {name: getattr(gate, name).__module__ for name in FROZEN_CALLABLE_SURFACE}
    assert observed == dict.fromkeys(FROZEN_CALLABLE_SURFACE, "check_csrf_exempt_gate")


@pytest.mark.parametrize(
    ("expression", "verdict"),
    TRUTHINESS_CASES,
    ids=[case[0] for case in TRUTHINESS_CASES],
)
def test_literal_truthiness_keeps_its_pre_split_verdict(
    expression: str, verdict: bool | None
) -> None:
    """Every captured fold result survives the decomposition unchanged."""
    node = ast.parse(expression, mode="eval").body
    assert gate._literal_truthiness(node) is verdict


def test_clean_scan_keeps_its_exact_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty module tree keeps the pre-split success line and exit code."""
    (tmp_path / "quickscale_modules").mkdir()
    assert gate.main([str(tmp_path)]) == 0
    assert capsys.readouterr().out == CLEAN_OUTPUT


def test_missing_modules_directory_keeps_its_exact_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repo root without the module workspace keeps its pre-split diagnostic."""
    absent = (tmp_path / "quickscale_modules").resolve()
    assert gate.main([str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"ERROR: Modules directory not found: {absent}\n"


def test_violation_keeps_its_exact_findings_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A violating module keeps the pre-split header, line, and hard-fail block."""
    source_dir = tmp_path / "quickscale_modules" / "demo" / "src"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "views.py"
    source_file.write_text(VIOLATING_SOURCE, encoding="utf-8")
    lineno = ast.parse(VIOLATING_SOURCE).body[-1].lineno

    assert gate.main([str(tmp_path)]) == 1
    assert capsys.readouterr().out == (
        "[demo] Unprotected csrf_exempt usage:\n"
        f"  views.py:{lineno}  function get applies csrf_exempt without calling an "
        "approved verification helper (_enforce_csrf)\n"
        "\n"
        "❌ 1 unprotected csrf_exempt usage(s) found (hard-fail after SA46).\n"
        "Every csrf_exempt callsite must call one of:\n"
        "    _enforce_csrf\n"
        "\n"
    )
