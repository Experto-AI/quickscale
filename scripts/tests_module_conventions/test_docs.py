"""Control cases for the docs module-convention rules."""

from __future__ import annotations

from dataclasses import replace

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _golden_module,
    _violations,
)


def test_readme_content_control() -> None:
    module = _golden_module()
    broken = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "`api_rate_limit` - throttle rate.", ""
            ),
        },
    )
    assert any(
        "api_rate_limit" in violation
        for violation in _violations(checker.rule_38_readme_content, broken)
    )
