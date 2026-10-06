"""Control cases for the core module-convention rules."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    GOLDEN_README,
    REPO_ROOT,
    _corpus,
    _golden_module,
)


def test_golden_fixture_passes_every_covered_rule() -> None:
    module = _golden_module()
    corpus = _corpus(module)
    failed = {rule.number: rule.detector(corpus) for rule in checker.RULES if rule.detector(corpus)}
    assert failed == {}


def test_malformed_tree_returns_violations_not_tracebacks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module_dir = tmp_path / "quickscale_modules" / "demo"
    package = module_dir / "src" / "quickscale_modules_demo"
    package.mkdir(parents=True)
    (module_dir / "module.yml").write_text(
        "name: demo\nconfig:\n  mutable:\n    1:\n      type: string\nrequired_modules: 1\n",
        encoding="utf-8",
    )
    (module_dir / "README.md").write_text(GOLDEN_README, encoding="utf-8")
    (package / "__init__.py").write_text('"""Demo."""\n', encoding="utf-8")
    (package / "views.py").write_text(
        "from quickscale_modules_notifications.services import send_notification\n",
        encoding="utf-8",
    )
    assert checker.check_conventions(tmp_path)
    assert checker.main([str(tmp_path)]) == 1
    assert "VIOLATION:" in capsys.readouterr().out


def test_layer_table_mirrors_the_shipped_modules() -> None:
    corpus = checker.load_corpus(REPO_ROOT)
    assert {module.name for module in corpus.modules} == set(checker.MODULE_LAYERS)


def _decisions_document() -> str:
    path = REPO_ROOT / checker.DECISIONS_DOC_RELATIVE_PATH
    return path.read_text(encoding="utf-8")


def test_decisions_rule_headings_partition_into_covered_open_or_delegated() -> None:
    recorded = checker.decisions_rule_numbers(REPO_ROOT)
    covered = {rule.number for rule in checker.RULES}
    open_rules = {number for number, _ in checker.OPEN_RULES}
    delegated = {number for number, _ in checker.DELEGATED_RULES}
    assert covered.isdisjoint(open_rules | delegated)
    assert open_rules.isdisjoint(delegated)
    assert checker.partition_violations(recorded) == []


def test_partition_control_rejects_an_unlisted_rule_heading() -> None:
    document = _decisions_document().replace(
        "**1. Settings names.**",
        "**999. Unlisted rule.**\n\n**1. Settings names.**",
        1,
    )
    recorded = checker.rule_numbers_in_decisions(document)
    assert 999 in recorded
    assert checker.partition_violations(recorded) == [
        "rule 999 is neither covered, open, nor delegated"
    ]


def test_main_success_line_names_the_delegated_rules(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert checker.main([str(REPO_ROOT)]) == 0
    out = capsys.readouterr().out
    assert "delegated:" in out
    delegated = out.split("delegated:", 1)[1]
    for number, _ in checker.DELEGATED_RULES:
        assert f"{number} (" in delegated


def test_every_open_rule_names_its_closer() -> None:
    for number, closer in checker.OPEN_RULES:
        assert re.search(r"SA\d+", closer), f"rule {number} needs a closing ticket: {closer!r}"


def test_every_delegated_rule_names_its_carrier() -> None:
    for number, carrier in checker.DELEGATED_RULES:
        assert carrier.strip(), f"rule {number} needs a recorded carrier"


def test_covered_rules_are_unique_and_numbered() -> None:
    numbers = [rule.number for rule in checker.RULES]
    assert numbers == sorted(numbers)
    assert len(numbers) == len(set(numbers))


def test_live_tree_passes_the_harness() -> None:
    assert checker.check_conventions(REPO_ROOT) == []


def test_missing_modules_root_is_authority_failure(tmp_path: Path) -> None:
    with pytest.raises(checker.AuthorityError):
        checker.load_corpus(tmp_path)


def test_main_reports_authority_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert checker.main([str(tmp_path)]) == 2
    assert "ERROR:" in capsys.readouterr().err
