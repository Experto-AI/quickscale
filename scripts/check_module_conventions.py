#!/usr/bin/env python3
"""
Module Conventions conformance check: rule 40's enforcement harness.

Rule 40 requires one conformance test over every ``module.yml``, every
module's source, and core's and the CLI's option handling that fails on each
of the Module Conventions rules the harness covers.  This check runs the
detectors for the rules the shipped tree already meets.  Each detector has a
control case in ``scripts/tests_module_conventions/`` proving it rejects
a violation.  Rules not yet enforced here are recorded in ``OPEN_RULES`` with
the ticket or mechanism that closes them, and the test suite keeps the two sets
a partition of the recorded rule numbers.

Each covered rule is enforced over the statically checkable clauses of the
rule; SA215 extends the harness to the rules and clauses still open.

Exit codes:
    0: every covered rule's detector found no violation.
    1: one or more violations were found.
    2: the repository tree could not be trusted.
"""

# Direct execution (`python scripts/check_module_conventions.py`) needs the
# repository root on sys.path before the package imports below.
# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.module_conventions.core import (
    MODULE_LAYERS,
    AuthorityError,
    Corpus,
    Module,
    load_corpus,
)
from scripts.module_conventions.registry import (
    OPEN_RULES,
    RULES,
    check_conventions,
)
from scripts.module_conventions.rule_44 import (
    rule_44_role_checks,
)
from scripts.module_conventions.rules_analytics import (
    rule_22_analytics_events,
)
from scripts.module_conventions.rules_dependencies import (
    rule_5_dependency_direction,
    rule_35_secrets,
    rule_36_typecheck_config,
    rule_39_module_dependencies,
)
from scripts.module_conventions.rules_docs import (
    rule_38_readme_content,
)
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
    THEME_SEAM_TEMPLATE,
    THEME_SEAM_TEMPLATES,
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
from scripts.module_conventions.rules_webhooks import (
    rule_26_webhooks,
)

__all__ = [
    "AuthorityError",
    "Corpus",
    "MODULE_LAYERS",
    "Module",
    "OPEN_RULES",
    "RULES",
    "THEME_SEAM_TEMPLATE",
    "THEME_SEAM_TEMPLATES",
    "check_conventions",
    "load_corpus",
    "main",
    "rule_10_checks_errors",
    "rule_11_package_files",
    "rule_12_manifest_options",
    "rule_13_tenant_models",
    "rule_14_model_basics",
    "rule_15_package_root",
    "rule_16_signals",
    "rule_17_management_commands",
    "rule_18_package_tooling",
    "rule_19_authorization",
    "rule_1_settings_names",
    "rule_20_email",
    "rule_22_analytics_events",
    "rule_23_service_surface",
    "rule_24_small_conventions",
    "rule_25_constraint_names",
    "rule_26_webhooks",
    "rule_28_file_names",
    "rule_29_test_names",
    "rule_2_identity_names",
    "rule_31_theme_seam",
    "rule_32_throttles",
    "rule_33_shared_stems",
    "rule_34_name_references",
    "rule_35_secrets",
    "rule_36_typecheck_config",
    "rule_37_module_lists",
    "rule_38_readme_content",
    "rule_39_module_dependencies",
    "rule_3_settings_reads",
    "rule_42_settings_snapshots",
    "rule_43_optional_senders",
    "rule_44_role_checks",
    "rule_45_stub_exemptions",
    "rule_47_redaction",
    "rule_48_replacement_values",
    "rule_4_public_surface",
    "rule_5_dependency_direction",
    "rule_6_no_legacy_names",
    "rule_7_urls",
    "rule_8_templates",
    "rule_9_http_apis",
]


def main(argv: list[str] | None = None) -> int:
    """Run the rule 40 conformance check."""
    args = sys.argv[1:] if argv is None else argv
    repo_root = Path(args[0]).resolve() if args else Path.cwd().resolve()
    try:
        violations = check_conventions(repo_root)
    except AuthorityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for violation in violations:
        print(f"VIOLATION: {violation}")
    if violations:
        print(f"Found {len(violations)} module convention violation(s).")
        return 1
    covered = ", ".join(str(rule.number) for rule in RULES)
    print(f"All {len(RULES)} covered module conventions pass (rules {covered}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
