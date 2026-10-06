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


# Rules the harness must cover or record as open.  SA215 covered 1-39;
# SA236 adds 42-43; SA235's rule 41 clauses live in rules 7, 31, and 37, and
# SA238's rule 46 clauses live in rules 19 and 28.  SA237 adds 44-45.
# SA245 adds 47-48; SA248 adds 50.
RECORDED_RULE_NUMBERS = frozenset({*range(1, 40), 42, 43, 44, 45, 47, 48, 50})


def test_covered_and_open_rules_partition_the_recorded_rules() -> None:
    covered = {rule.number for rule in checker.RULES}
    open_rules = {number for number, _ in checker.OPEN_RULES}
    assert covered | open_rules == RECORDED_RULE_NUMBERS
    assert not covered & open_rules


def test_every_open_rule_names_its_closer() -> None:
    for number, closer in checker.OPEN_RULES:
        assert re.search(r"SA\d+", closer), f"rule {number} needs a closing ticket: {closer!r}"


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
