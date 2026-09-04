# QuickScale Documentation

**Quick Start**: New to QuickScale? Start with [../START_HERE.md](../START_HERE.md)

---

## Core Documentation

- **Getting Started**
  - [START_HERE.md](../START_HERE.md) - Documentation guide with decision tree
  - [README.md](../README.md) - Project overview and quick start
  - [GLOSSARY.md](../GLOSSARY.md) - Centralized terminology reference

- **Technical**
  - [Decisions (authoritative)](technical/decisions.md) - Technical rules and architectural decisions
  - [Scaffolding (layout & templates)](technical/scaffolding.md) - Directory structures and file layouts
  - [Roadmap](technical/roadmap.md) - Development timeline and current tasks
  - [v88 Ticket Context](technical/v88_ticket_context.md) - Current v88 ledger: SA167c remains open at #21 with phases A-E accepted on retained product object `91fd3bb6e6b638735361b511c1515cddccce5d15`; F remains outstanding after `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` exited 2 with 2 Core and 8 CLI E2E failures owned by SA170/W3; retained-partial-only merge-back of its synchronized nine-file status checkpoint is authorized without accepting F, closing SA167c, or unblocking SA166, while exact-tip attestation is complete and that checkpoint merged at `ef712e2d649d73aec0bdd9b4d3ca0b23913da419`; SA170's dependency and return-141 static blockers remain repaired, but its latest ordered serial campaign used `setsid --wait env QS_E2E_PARALLEL=0 QS_E2E_INTEGRATION_REF=v88 make test-e2e` and exited 2 with Core 38 passed and CLI 52 passed / 1 failed at the installed-wheel lifecycle row after `poetry install` aborted following dependency synchronization; the concurrent `make ci-e2e` campaign was not run because the serial prerequisite was red; exact-scope cleanup and standing PostgreSQL equality passed, but the other three frozen rows lack individual pass oracles; a convergence-only focused rerun of the installed-wheel row and a diagnostic-copy `poetry install -vvv` both passed, without retroactively greening the campaign or identifying its unretained lower-level cause; SA170 remains open and TA70 remains live pending a fresh ordered serial-then-concurrent campaign with cleanup and PostgreSQL equality, SA167c remains halted, and no completion or release-readiness claim or downstream unblocking is made; SA167d's completion-grade closeout is a conditional post-integration candidate with exact-tip integration pending; SA165's phases A-C are accepted on retained product object `573a57a34301e6a91971a7845095bd913bebd5e1`, merged at `3f925b96` as retained partial delivery, with Phase D held by the same SA170-owned red release gate; SA174 (#31) and SA175 (#32) moved from W1 to W2 on 2026-09-03, making lanes W1 3 · W2 5 · W3 3; eleven open v88 ticket entries across eleven open merge positions
  - [User Manual](technical/user_manual.md) - Commands and workflows
  - [Development](technical/development.md) - Dev environment setup
  - [Plan/Apply System](technical/plan-apply-system.md) - Terraform-style workflow
  - [Module Extension Contract](technical/module-extension.md) - Extension surfaces, support tiers, and per-module contracts

- **Overview**
  - [QuickScale Strategic Vision](overview/quickscale.md) - Creator-led positioning and current evolution rationale
  - [Competitive Analysis](overview/competitive_analysis.md) - Concise comparison with Django starter alternatives
  - [Commercial Extensions](overview/commercial.md) - Current commercial-use rights and constraints
  - [Packages](overview/packages.md) - Current package naming and surface notes

- **Contributing**
  - [Contributing Guide](contrib/contributing.md) - Development workflow overview
  - [Code Guide](contrib/code.md) - Implementation principles
  - [Review Guide](contrib/review.md) - Quality control
  - [Testing Guide](contrib/testing.md) - Test generation
  - [Debug Guide](contrib/debug.md) - Debugging and root cause analysis

- **Planning**
  - [Beta Site Migration Playbook](planning/beta-site-migration.md) - Step-by-step guide for keeping experto-ai-web and bap-web current with new QuickScale releases
  - [Analytics Provider Comparison](planning/analytics-provider-comparison.md) - Provider evaluation for analytics implementation planning
  - [Email Sender Comparison](planning/email-sender-comparison.md) - Provider evaluation for notification delivery planning
  - [Frontend E2E Coverage](planning/frontend-e2e-coverage.md) - Status, gap analysis, and options for React-theme browser and journey testing

- **Others** (working notes; not authoritative)
  - [Architectural Audit](others/arch-audit.md) - Live structural findings
  - [Technical Audit](others/tech-audit.md) - Live defect posture
  - [Adaptive](others/adaptive.md) - Adaptive agent pipeline notes
  - [Automation](others/automation.md) - Automation notes

- **Deployment**
  - [Railway Deployment](deployment/railway.md) - Deploy to Railway platform

- **Releases**
  - [Release Notes](releases/) - Official tagged GitHub release notes for published releases
  - [Release Summary Template](technical/release_summary_template.md) - Template for the single public release-note workflow

---

**Documentation Principles**:
- [decisions.md](technical/decisions.md) is authoritative for technical rules
- [GLOSSARY.md](../GLOSSARY.md) is authoritative for terminology
- Update Tier 1 docs first, then propagate changes
