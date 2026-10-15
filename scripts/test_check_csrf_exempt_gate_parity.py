"""
Behavioral controls for the SA267(c) ``check_csrf_exempt_gate`` refactor.

SA267 has closed, so SA278 retired the pre-split surface pins; these controls
keep the exact truthiness verdicts captured from the pre-split fold and the
gate's exact findings output as behavioral tests, so a later change cannot
silently drop, relocate, or reword them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import check_csrf_exempt_gate as gate
import pytest

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
