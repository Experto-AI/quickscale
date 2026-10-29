# QuickScale Documentation

New here: [START_HERE.md](../START_HERE.md). **A** marks an authoritative document. Its
rules are binding and use MUST / MUST NOT wording. decisions.md wins any conflict, and
[§ Document Responsibilities](technical/decisions.md#document-responsibilities) names each topic's owner.

## Entry points
- [README.md](../README.md): overview, quick start, packages
- [GLOSSARY.md](../GLOSSARY.md) **A**: terminology
- [CHANGELOG.md](../CHANGELOG.md): release history; [releases/](releases/): one note per version

## Technical
- [decisions.md](technical/decisions.md) **A**: repo-wide rules, prohibitions, document ownership
- [implementation_contract.md](technical/implementation_contract.md) **A**: shipped contract and CLI surface
- [module_architecture.md](technical/module_architecture.md) **A**: plan/apply state, module manifest, derivation, wiring, inventory
- [module_conventions.md](technical/module_conventions.md) **A**: numbered module conventions (rules 1–50)
- [release_gates_policy.md](technical/release_gates_policy.md) **A**: version lockstep, gate coverage and budget, quality thresholds
- [validation_policy.md](technical/validation_policy.md) **A**: validation entrypoints, testing and coverage
- [generated_project_structure.md](technical/generated_project_structure.md) **A**: generated-project layout
- [repository_layout.md](technical/repository_layout.md) **A**: maintainer-repo layout, naming and imports
- [module-extension.md](technical/module-extension.md) **A**: module extension contract and authoring checklist
- [generated_file_ownership.md](technical/generated_file_ownership.md) **A**: website-migration generated-file ownership rules and inventory
- [migration_upgrade_path.md](technical/migration_upgrade_path.md) **A**: website-migration two-stage upgrade path, boundary rule, revocation triggers
- [publish_procedure.md](technical/publish_procedure.md) **A**: pre-publish gate, release phases, release-note format
- [plan-apply-system.md](technical/plan-apply-system.md): plan/apply schemas and execution order
- [frontend.md](technical/frontend.md): Django/React seam, URL ownership, static pipeline
- [organizations.md](technical/organizations.md): multi-tenant orgs model
- [quality_tools.md](technical/quality_tools.md): analyzers and threshold gate
- [versioning.md](technical/versioning.md): `VERSION` single source
- [roadmap.md](technical/roadmap.md): open work and scheduling
- [user_manual.md](technical/user_manual.md): `quickscale` CLI workflows and examples
- [development.md](technical/development.md): contributor environment, repository commands, E2E setup, local wheelhouse
- [docker_workflows.md](technical/docker_workflows.md): Docker workflows
- [ai_context.md](technical/ai_context.md): compact AI hydration baseline (derived, never authoritative)
- [ai_hydration_topology.md](technical/ai_hydration_topology.md) **A**: Adaptive wiring and which docs each agent role hydrates

## Contributing
- [contrib/contributing.md](contrib/contributing.md): guide map
- [contrib/rules.md](contrib/rules.md) **A**: contributor engineering rules
- Stage guides: [plan](contrib/plan.md), [code](contrib/code.md), [review](contrib/review.md), [testing](contrib/testing.md), [debug](contrib/debug.md)

## Overview
- [positioning.md](overview/positioning.md): positioning, comparison with alternatives, commercial use

## Operations
- [deployment/railway.md](deployment/railway.md): deploy to Railway; [operations](deployment/railway-operations.md) (backups, DR, media), [config as code](deployment/railway-config-as-code.md), [troubleshooting](deployment/railway-troubleshooting.md)
- [planning/beta-site-migration.md](planning/beta-site-migration.md): keep `bap-web` current with releases

## Audits (open findings only; not authoritative)
- [arch-audit.md](others/arch-audit.md), [tech-audit.md](others/tech-audit.md), [coherence-audit.md](others/coherence-audit.md)
