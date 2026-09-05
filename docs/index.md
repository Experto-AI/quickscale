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
  - [v88 Ticket Context](technical/v88_ticket_context.md) - Current v88 ledger: nine open v88 ticket entries across nine open merge positions, lanes W1 4 · W2 4 · W3 1 after the 2026-09-05 in-lane ticket splits (SA164 → SA164 + SA178, SA165 → SA165 + SA179, SA172 → SA172 + post-v88 SA177); SA170/TA70, SA167c (EV-7), and SA166 are archived after accepted closeouts; SA164 now heads W2 with `deps: none`; SA165 heads W1 with `deps: none` as an integrated retained partial with SA165-R1 still tracked and one replacement release verdict authorized as EV-8, now scoped to its product-only candidate; SA171 is release-accepted after SA176 preserved the serialized acquisition key and restored the full `make ci` gate, so SA172 now heads W3 with `deps: none`; no open ticket remains on the release critical path and no maintainer decision is open
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
