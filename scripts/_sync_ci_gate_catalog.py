#!/usr/bin/env python3
"""
Private sibling: the static gate catalog for ``sync_ci_gate_jobs`` (SA267).

Marker strings, display metadata, ordering, and the helper-owned catalogs the
generator validates every registry against.  The facade re-exports this
module's names; the projection and CLI siblings import the defining names
directly.
"""

from __future__ import annotations

from dataclasses import dataclass

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

HOSTED_GATE_ORDER = (
    "check-core-compat",
    "check-module-core-imports",
    "check-manifest-sync",
    "check-module-app-declaration",
    "check-org-context-primitives",
    "check-csrf-exempt",
    "check-commit-testimony",
    "check-project-contract-vintage",
    "check-gate-suites",
    "check-dependency-vulnerabilities",
    "check-security-static-analysis",
    "check-beta-migration-smoke",
    "check-generated-deploy-posture",
    "check-workflow-security",
    "check-secret-scanning",
    "check-module-conventions",
    "check-split-facade-imports",
)

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
NEEDS_GATE_IDS = {
    "test": HOSTED_GATE_ORDER,
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


@dataclass(frozen=True)
class HostedJobSpec:
    """Static presentation and execution metadata for one hosted gate."""

    display_name: str
    check_step_name: str
    full_history: bool = False


HOSTED_JOB_CATALOG: dict[str, HostedJobSpec] = {
    "check-core-compat": HostedJobSpec(
        "Module-vs-Oldest-Core Compatibility",
        "Run module-vs-core compatibility check (static analysis + install/import probe)",
    ),
    "check-module-core-imports": HostedJobSpec(
        "Module-Core Import Linter",
        "Run module-core import linter",
    ),
    "check-manifest-sync": HostedJobSpec(
        "Manifest Sync Gate (SA16.1)",
        "Verify module manifests match core snapshots",
    ),
    "check-module-app-declaration": HostedJobSpec(
        "Module App Declaration Gate (SA167c)",
        "Verify evidence-bearing modules declare Django apps wiring",
    ),
    "check-org-context-primitives": HostedJobSpec(
        "Org-Context Primitives Gate (SA13.4)",
        "Verify no external use of privatized org-context primitives",
    ),
    "check-csrf-exempt": HostedJobSpec(
        "CSRF-Exempt Gate (SA46)",
        "Verify every csrf_exempt callsite pairs with _enforce_csrf or signature verification",
    ),
    "check-commit-testimony": HostedJobSpec(
        "Behavioural Commit Testimony Gate (SA166)",
        "Verify behavioural commits carry a vNN roadmap reference",
        full_history=True,
    ),
    "check-project-contract-vintage": HostedJobSpec(
        "Project Contract Vintage Gate (SA207)",
        "Verify generated-template and module-manifest contract changes declare a new step id",
        full_history=True,
    ),
    "check-gate-suites": HostedJobSpec(
        "Registered Script Gate Suites",
        "Run registered scripts test suites",
    ),
    "check-dependency-vulnerabilities": HostedJobSpec(
        "Dependency Vulnerability Gate (SA123)",
        "Run dependency vulnerability gate",
    ),
    "check-security-static-analysis": HostedJobSpec(
        "Security Static Analysis Gate (SA123)",
        "Run security static-analysis gate",
    ),
    "check-beta-migration-smoke": HostedJobSpec(
        "Beta Migration Smoke Gate (SA152)",
        "Run beta migration smoke gate",
    ),
    "check-generated-deploy-posture": HostedJobSpec(
        "Generated Deploy Posture Gate (SA200)",
        "Run generated-project deploy posture gate",
    ),
    "check-workflow-security": HostedJobSpec(
        "Workflow Security Gate (SA202)",
        "Run workflow security gate",
    ),
    "check-secret-scanning": HostedJobSpec(
        "Secret Scanning Gate (SA202)",
        "Run secret scanning gate",
    ),
    "check-module-conventions": HostedJobSpec(
        "Module Conventions Gate (rule 40)",
        "Run module conventions conformance check",
    ),
    "check-split-facade-imports": HostedJobSpec(
        "Split-Facade Import Gate (SA234)",
        "Reject a private module importing a facade in its distribution",
    ),
}


@dataclass(frozen=True)
class PublishStepSpec:
    """Static presentation metadata for one generated publish gate step."""

    step_name: str
    command_prefix: str | None = None


# The publish workflow's gate steps, in their owned display order.  Membership
# is validated against the registry's ``publish`` context, so adding or
# removing a publish-bound gate fails closed until this catalog is updated
# alongside it; every step's command derives its Make target from the
# registry binding, and only the vintage step's environment assignment is
# static.
PUBLISH_GATE_ORDER = (
    "check-core-compat",
    "check-module-core-imports",
    "check-manifest-sync",
    "check-org-context-primitives",
    "check-csrf-exempt",
    "check-project-contract-vintage",
    "check-dependency-vulnerabilities",
    "check-security-static-analysis",
    "check-beta-migration-smoke",
    "check-generated-deploy-posture",
    "check-workflow-security",
    "check-secret-scanning",
    "check-module-conventions",
    "check-split-facade-imports",
    "frontend-proof",
    "smoke-install",
)

PUBLISH_STEP_CATALOG: dict[str, PublishStepSpec] = {
    "check-core-compat": PublishStepSpec("Run core compatibility gate"),
    "check-module-core-imports": PublishStepSpec("Run module core imports gate"),
    "check-manifest-sync": PublishStepSpec("Run manifest sync gate"),
    "check-org-context-primitives": PublishStepSpec("Run org context primitives gate"),
    "check-csrf-exempt": PublishStepSpec("Run CSRF exempt gate"),
    "check-project-contract-vintage": PublishStepSpec(
        "Run project contract vintage gate",
        "PROJECT_VINTAGE_BASE_REF=\"$(git describe --tags --abbrev=0 'HEAD^' "
        '2>/dev/null || git rev-list --max-parents=0 HEAD | tail -n 1)"',
    ),
    "check-dependency-vulnerabilities": PublishStepSpec("Run dependency vulnerability gate"),
    "check-security-static-analysis": PublishStepSpec("Run security static-analysis gate"),
    "check-beta-migration-smoke": PublishStepSpec("Run beta migration smoke gate"),
    "check-generated-deploy-posture": PublishStepSpec("Run generated deploy posture gate"),
    "check-workflow-security": PublishStepSpec("Run workflow security gate"),
    "check-secret-scanning": PublishStepSpec("Run secret scanning gate"),
    "check-module-conventions": PublishStepSpec("Run module conventions conformance check"),
    "check-split-facade-imports": PublishStepSpec("Run split-facade import gate"),
    "frontend-proof": PublishStepSpec("Run rendered frontend proof"),
    "smoke-install": PublishStepSpec("Run installed-artifact smoke gate (SA110)"),
}

# Curated Makefile comments for the generated gate targets, preserving the
# operational hints the hand-written recipes carried.  Display-only metadata
# (like HOSTED_JOB_CATALOG); a gate without an entry falls back to its
# registry description.
MAKE_TARGET_COMMENTS: dict[str, str] = {
    "check-core-compat": (
        "Check each module's quickscale_core imports against the current core API.\n"
        "This verifies that every import from quickscale_core in a module's source\n"
        "resolves to an existing symbol, and that the module's quickscale-core\n"
        "specifier is exactly the lockstep pin derived from VERSION."
    ),
    "check-module-core-imports": (
        "Check that module code only imports from quickscale_core.runtime\n"
        "(not from internal subpackages like dr_engine, contracts, manifest, etc.).\n"
        "Per-module legacy exceptions exist for billing/crm adapter seams only."
    ),
    "check-manifest-sync": (
        "Verify that every module-owned module.yml matches its core snapshot.\n"
        "Fails CI if drift is introduced.  Run ``make manifest-sync`` to\n"
        "resync snapshots after intentionally updating a module manifest."
    ),
    "check-module-app-declaration": (
        "Verify that evidence-bearing modules declare exactly one valid Django apps\n"
        "wiring projection in their authoritative source manifest."
    ),
    "check-org-context-primitives": (
        "Hard-fail lint gate for direct external use of the three privatized\n"
        "org-context primitives.  Exits 1 on any violation — all SA13.2/SA13.3\n"
        "migrations are complete.  AF9 None-path hardening deferred;\n"
        "compatibility aliases remain but trigger the gate."
    ),
    "check-csrf-exempt": (
        "Hard-fail AST gate that requires every csrf_exempt callsite to pair\n"
        "with _enforce_csrf or cryptographic signature verification.\n"
        "Exits 1 on any unprotected csrf_exempt usage."
    ),
    "check-commit-testimony": (
        "Inspect every non-merge commit in the selected base-to-head range. Changes\n"
        "to workflows, the gate registry, or PostgreSQL provisioning stations require\n"
        "a vNN roadmap reference in the commit message, bare (v88) or dotted\n"
        "(v0.88.0). No ticket form or changelog entry substitutes for it."
    ),
    "check-project-contract-vintage": (
        "Inspect every non-merge commit in the selected base-to-head range.  A change\n"
        "to any template the generator emits (the watched set derives from the\n"
        "generator's emission mapping), a generator change that alters the emitted\n"
        "file set, or a module manifest step whose text changes without a new id\n"
        "requires a fresh adoption step id in the same commit (the project\n"
        "declaration or the module manifest), so a generated-project contract change\n"
        "cannot ship without its adoption steps."
    ),
    "check-dependency-vulnerabilities": (
        "Public Make callers for the registry-bound scanner wrapper. Scanner\n"
        "acquisition, invocation, and suppression adjudication remain owned by the\n"
        "wrapper rather than being duplicated in Make recipes."
    ),
    "check-security-static-analysis": (
        "Public Make callers for the registry-bound scanner wrapper. Scanner\n"
        "acquisition, invocation, and suppression adjudication remain owned by the\n"
        "wrapper rather than being duplicated in Make recipes."
    ),
    "check-beta-migration-smoke": (
        "Exercise fresh-first migration behavior against isolated\n"
        "generated fixtures without touching a real project or database."
    ),
    "check-generated-deploy-posture": (
        "Render one fresh generated project and run Django's deployment checks in the\n"
        "proxied and single-host forwarding cells.  A new deploy warning, or an\n"
        "ungated SECURE_PROXY_SSL_HEADER in the single-host cell, fails the gate."
    ),
    "check-workflow-security": (
        "Fail on any zizmor finding at medium severity and confidence or above: an\n"
        "unpinned third-party `uses:` ref, or a workflow with no top-level\n"
        "`permissions:` block."
    ),
    "check-secret-scanning": (
        "Fail on any committed secret gitleaks reports after applying the reasoned\n"
        "allowlists in scripts/gitleaks.toml."
    ),
    "check-module-conventions": (
        "Run the rule 40 conformance check over every module manifest and module\n"
        "source tree.  Every covered rule's detector has a control case under\n"
        "scripts/tests_module_conventions/; the detectors live by rule theme under\n"
        "scripts/module_conventions/.  Rules whose owning convention ticket has not\n"
        "landed are recorded in the check's OPEN_RULES mapping."
    ),
    "check-split-facade-imports": (
        "Reject a private module importing a facade in its distribution (SA234)."
    ),
    "frontend-proof": (
        "Render showcase_react and prove the generated frontend toolchain without Docker"
    ),
    "smoke-install": (
        "Build wheels, install into throwaway venv outside source tree, and run\n"
        "non-mutating CLI smoke tests (SA110 installed-artifact smoke gate).\n"
        "Must run from the repository root with Poetry and a compatible Python."
    ),
    "quality": (
        "Full code quality analysis: dead code (vulture), complexity (radon), "
        "duplication (pylint)\n"
        "Reports saved to .quickscale/quality_report.{json,md}"
    ),
}
