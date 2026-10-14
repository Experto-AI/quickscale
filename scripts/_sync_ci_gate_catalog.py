#!/usr/bin/env python3
"""
Private sibling: the static gate wiring catalog for ``sync_ci_gate_jobs`` (SA267).

Marker strings, the consumer-``needs`` policy, and the hand-owned exemption
sets the generator validates every registry against.  Per-gate ordering and
presentation metadata (``hosted``, ``publish``, ``help``) are fields of
``gate_registry.json``, not catalog data (SA275a).  The facade re-exports this
module's names; the projection and CLI siblings import the defining names
directly.
"""

from __future__ import annotations

JOB_BEGIN = "  # BEGIN GENERATED: hosted-gate-jobs"
JOB_END = "  # END GENERATED: hosted-gate-jobs"
NEEDS_BEGIN = {
    "test": "    # BEGIN GENERATED: needs-test",
    "isolation-conformance": "    # BEGIN GENERATED: needs-isolation-conformance",
    "lint-cli": "    # BEGIN GENERATED: needs-lint-cli",
}
NEEDS_END = {
    "test": "    # END GENERATED: needs-test",
    "isolation-conformance": "    # END GENERATED: needs-isolation-conformance",
    "lint-cli": "    # END GENERATED: needs-lint-cli",
}
E2E_PATHS_BEGIN = "      # BEGIN GENERATED: e2e-trigger-paths"
E2E_PATHS_END = "      # END GENERATED: e2e-trigger-paths"
PUBLISH_BEGIN = "      # BEGIN GENERATED: publish-gate-steps"
PUBLISH_END = "      # END GENERATED: publish-gate-steps"
DOCS_TABLE_BEGIN = "<!-- BEGIN GENERATED: gate-registry-table -->"
DOCS_TABLE_END = "<!-- END GENERATED: gate-registry-table -->"
LOCAL_ARMS_BEGIN = "        # BEGIN GENERATED: local-gate-arms"
LOCAL_ARMS_END = "        # END GENERATED: local-gate-arms"
MAKEFILE_HELP_BEGIN = "\t@# BEGIN GENERATED: makefile-gate-help"
MAKEFILE_HELP_END = "\t@# END GENERATED: makefile-gate-help"

UNOWNED_JOB_RATIONALES = {
    "bypassrls": (
        "The reusable service-backed BYPASSRLS suite remains a separately owned hosted job."
    ),
    "lint-frontend": "Frontend toolchain validation remains a separately owned hosted job.",
    "backups-validation": (
        "Hosted PostgreSQL 18 service and client validation remains a fail-fast job."
    ),
    "module-manifest-contract": (
        "The ready-module contract is a separately owned hosted contract job."
    ),
    "test": (
        "The hosted unit and integration test job retains its service-backed workflow ownership."
    ),
    "isolation-conformance": (
        "Hosted-only service-backed isolation remains unowned pending later lifecycle work."
    ),
    "lint-cli": "CLI package linting remains a separately owned hosted package job.",
}
UNOWNED_JOB_IDS = frozenset(UNOWNED_JOB_RATIONALES)
EXPECTED_UNOWNED_JOB_IDS = frozenset(
    {
        "bypassrls",
        "lint-frontend",
        "backups-validation",
        "module-manifest-contract",
        "test",
        "isolation-conformance",
        "lint-cli",
    }
)
#: Hosted consumers that need every registry-bound hosted gate; the remaining
#: consumers derive their ``needs`` from the fixed needs plus the named gates.
NEEDS_ALL_HOSTED_CONSUMERS = ("test",)
NEEDS_GATE_IDS = {
    "isolation-conformance": (
        "check-manifest-sync",
        "check-org-context-primitives",
        "check-csrf-exempt",
        "check-gate-suites",
    ),
    "lint-cli": (
        "check-manifest-sync",
        "check-org-context-primitives",
        "check-csrf-exempt",
        "check-gate-suites",
    ),
}
FIXED_NEEDS = ("backups-validation", "module-manifest-contract")

# Registry gates whose Make recipe stays hand-written in the Makefile because
# it is not a command list (the conformance-suite aggregation runs a large
# inline shell program with its own process-identity guard).  Every other
# registry gate with a make_target must carry a make_recipe; generation fails
# closed otherwise, so a new gate cannot silently lose its Make target.
HAND_OWNED_MAKE_TARGETS = frozenset({"check-gate-suites"})
