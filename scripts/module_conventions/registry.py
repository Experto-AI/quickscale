"""The ordered rule registry and the entry-point check functions."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from scripts.module_conventions.core import (
    Corpus,
    load_corpus,
)
from scripts.module_conventions.rule_44 import rule_44_role_checks
from scripts.module_conventions.rules_analytics import rule_22_analytics_events
from scripts.module_conventions.rules_dependencies import (
    rule_5_dependency_direction,
    rule_35_secrets,
    rule_36_typecheck_config,
    rule_39_module_dependencies,
)
from scripts.module_conventions.rules_docs import rule_38_readme_content
from scripts.module_conventions.rules_identity import (
    rule_2_identity_names,
    rule_24_small_conventions,
    rule_28_file_names,
    rule_29_test_names,
    rule_33_shared_stems,
    rule_34_name_references,
    rule_37_module_lists,
)
from scripts.module_conventions.rules_misc import (
    rule_10_checks_errors,
    rule_20_email,
    rule_45_stub_exemptions,
    rule_50_notification_links,
)
from scripts.module_conventions.rules_models import (
    rule_13_tenant_models,
    rule_14_model_basics,
    rule_25_constraint_names,
)
from scripts.module_conventions.rules_package import (
    rule_4_public_surface,
    rule_6_no_legacy_names,
    rule_11_package_files,
    rule_15_package_root,
    rule_16_signals,
    rule_17_management_commands,
    rule_18_package_tooling,
    rule_23_service_surface,
)
from scripts.module_conventions.rules_redaction import (
    rule_47_redaction,
    rule_48_replacement_values,
)
from scripts.module_conventions.rules_routes import (
    rule_7_urls,
    rule_8_templates,
    rule_9_http_apis,
    rule_19_authorization,
    rule_31_theme_seam,
    rule_32_throttles,
)
from scripts.module_conventions.rules_settings import (
    rule_1_settings_names,
    rule_3_settings_reads,
    rule_12_manifest_options,
    rule_42_settings_snapshots,
    rule_43_optional_senders,
)
from scripts.module_conventions.rules_webhooks import rule_26_webhooks


@dataclass(frozen=True)
class Rule:
    """One covered Module Conventions rule and its detector."""

    number: int
    clause: str
    detector: Callable[[Corpus], list[str]]


RULES: tuple[Rule, ...] = (
    Rule(1, "settings names and the enabled switch", rule_1_settings_names),
    Rule(2, "identity names", rule_2_identity_names),
    Rule(3, "reading settings", rule_3_settings_reads),
    Rule(4, "how one module uses another", rule_4_public_surface),
    Rule(5, "dependency direction", rule_5_dependency_direction),
    Rule(6, "no legacy names", rule_6_no_legacy_names),
    Rule(7, "URL mounts and route names", rule_7_urls),
    Rule(8, "templates, static files, template tags", rule_8_templates),
    Rule(9, "HTTP APIs", rule_9_http_apis),
    Rule(10, "checks, errors, core ports", rule_10_checks_errors),
    Rule(11, "package files, tests, and one-off file privatization", rule_11_package_files),
    Rule(12, "manifest option schema", rule_12_manifest_options),
    Rule(13, "tenant models", rule_13_tenant_models),
    Rule(14, "model basics", rule_14_model_basics),
    Rule(15, "package root", rule_15_package_root),
    Rule(16, "signals", rule_16_signals),
    Rule(17, "management commands", rule_17_management_commands),
    Rule(18, "package tooling", rule_18_package_tooling),
    Rule(19, "authorization by org role", rule_19_authorization),
    Rule(20, "email", rule_20_email),
    Rule(22, "analytics events", rule_22_analytics_events),
    Rule(23, "service surface", rule_23_service_surface),
    Rule(24, "small conventions", rule_24_small_conventions),
    Rule(25, "constraint and index names", rule_25_constraint_names),
    Rule(26, "inbound webhooks", rule_26_webhooks),
    Rule(28, "module file names", rule_28_file_names),
    Rule(29, "test names", rule_29_test_names),
    Rule(31, "the theme seam", rule_31_theme_seam),
    Rule(32, "throttles", rule_32_throttles),
    Rule(
        33,
        "shared-namespace stems (database functions and advisory-lock keys)",
        rule_33_shared_stems,
    ),
    Rule(34, "references by name", rule_34_name_references),
    Rule(35, "secrets", rule_35_secrets),
    Rule(36, "type-check configuration", rule_36_typecheck_config),
    Rule(37, "module lists outside the modules", rule_37_module_lists),
    Rule(38, "README content", rule_38_readme_content),
    Rule(39, "module dependencies", rule_39_module_dependencies),
    Rule(42, "settings snapshots", rule_42_settings_snapshots),
    Rule(43, "optional senders", rule_43_optional_senders),
    Rule(44, "one role check", rule_44_role_checks),
    Rule(45, "stub exemptions", rule_45_stub_exemptions),
    Rule(47, "redaction", rule_47_redaction),
    Rule(48, "replacement values and entry-point name", rule_48_replacement_values),
    Rule(50, "notification person links", rule_50_notification_links),
)


# Rules the harness does not yet cover: their remaining code change has not
# landed, or another gate already enforces them.  The coverage test keeps this
# a partition with RULES over the recorded rules, so no rule can be silently
# omitted.
OPEN_RULES: tuple[tuple[int, str], ...] = (
    (21, "SA216 (rule 21 is a review rule; each module's write-effect rollback test)"),
    (27, "SA215 (user-FK conformance gate orgs/tests/test_user_fk_conformance.py)"),
    (30, "SA215 (enforced in apply itself, core collect_wiring)"),
)


# Rules with no detector of their own, listed with the carrier that enforces
# them: rule 40 is the conformance-test rule this harness and its control cases
# are; 41's and 46's clauses ride the covered rules named; 49's gate is the
# closed-world inventory test and orgs' W006 check.  The partition test keeps
# covered, open, and delegated a partition of the rule headings decisions.md
# declares, so no rule can be silently omitted.
DELEGATED_RULES: tuple[tuple[int, str], ...] = (
    (40, "this harness"),
    (41, "rules 7, 31 and 37"),
    (46, "rules 19 and 28"),
    (49, "the inventory test and orgs' W006 check"),
)

DECISIONS_DOC_RELATIVE_PATH = Path("docs/technical/decisions.md")
MODULE_CONVENTIONS_HEADING = "### Module Conventions"
_RULE_HEADING = re.compile(r"^\*\*(\d+)\.\s")


def rule_numbers_in_decisions(text: str) -> tuple[int, ...]:
    """Return the rule numbers decisions.md declares under Module Conventions."""
    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.startswith(MODULE_CONVENTIONS_HEADING)),
        None,
    )
    if start is None:
        raise ValueError(f"decisions.md has no {MODULE_CONVENTIONS_HEADING!r} section")
    numbers: list[int] = []
    for line in lines[start + 1 :]:
        if line.startswith("#"):
            break
        match = _RULE_HEADING.match(line)
        if match:
            numbers.append(int(match.group(1)))
    if not numbers:
        raise ValueError("decisions.md § Module Conventions declares no numbered rules")
    return tuple(numbers)


def decisions_rule_numbers(repo_root: Path) -> tuple[int, ...]:
    """Return the rule numbers decisions.md declares, read under repo_root."""
    text = (repo_root / DECISIONS_DOC_RELATIVE_PATH).read_text(encoding="utf-8")
    return rule_numbers_in_decisions(text)


def partition_violations(recorded: Iterable[int]) -> list[str]:
    """Return messages for headings with no entry and for entries with no heading."""
    known = {rule.number for rule in RULES}
    known |= {number for number, _ in OPEN_RULES}
    known |= {number for number, _ in DELEGATED_RULES}
    recorded_numbers = list(recorded)
    violations = [
        f"rule {number} is neither covered, open, nor delegated"
        for number in recorded_numbers
        if number not in known
    ]
    violations.extend(
        f"rule {number} is registered but decisions.md declares no such rule heading"
        for number in sorted(known - set(recorded_numbers))
    )
    return violations


def check_conventions(repo_root: Path) -> list[str]:
    """Return sorted violations for every covered rule."""
    corpus = load_corpus(repo_root)
    violations: list[str] = []
    for rule in RULES:
        try:
            violations.extend(rule.detector(corpus))
        except SyntaxError as exc:
            violations.append(f"rule {rule.number}: unparsable module source: {exc}")
    return sorted(set(violations))
