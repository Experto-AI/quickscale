# QuickScale Release Archive

**Purpose**: Historical record for archived QuickScale releases, combining older implementation/review artifacts with newer mixed-layout release records as they are published. This archive preserves implementation/review artifacts while keeping active documentation focused on current and future releases.

**For Current Roadmap**: See [roadmap.md](./roadmap.md)

**For Recent Reader-Facing Summaries**: See [../releases/](../releases/)

**For Detailed Release Documents**: See [../releases-archive/](../releases-archive/) directory

---

## Release Summary Table

Dates and short summaries below mirror the linked release artifacts and [CHANGELOG.md](../../CHANGELOG.md). The table is ordered by version, not by time; the date column records the linked artifact date when one exists and otherwise falls back to the changelog entry.

| Version | Artifact Date | Phase | Key Changes | Status | Docs |
|---------|---------------|-------|-------------|--------|------|
| **v0.78.0** | 2026-03-30 | Post-MVP | Notifications module, app-owned rendering, recipient-granular delivery tracking, and post-MVP expansion kickoff | ✅ Complete | [Summary](../releases/release-v0.78.0.md) |
| **v0.77.0** | 2026-03-31 | MVP | Backups module MVP closeout baseline with private local/remote workflows and retrospective archival notes | ✅ Archived retrospective | [Impl](../releases-archive/release-v0.77.0-implementation.md) |
| **v0.76.0** | 2026-03-21 | MVP | Storage module, canonical public media URLs, `public_base_url` contract cleanup | ✅ Complete | [Summary](../releases/release-v0.76.0.md) |
| **v0.75.0** | 2026-02-23 | MVP | Forms module with admin-managed schemas, DRF API, spam protection, and notifications | ✅ Complete | [Summary](../releases/release-v0.75.0.md) |
| **v0.74.0** | 2026-02-05 | MVP | React default theme (`showcase_react`) with Vite, TypeScript, TanStack Query, and Zustand | ✅ Complete | [Summary](../releases/release-v0.74.0.md) |
| **v0.73.0** | 2026-02-04 | MVP | CRM module with API-first Django app structure and CLI integration | ✅ Complete | [Impl](../releases-archive/release-v0.73.0-implementation.md) |
| **v0.72.0** | 2025-12-07 | MVP | Plan/Apply cleanup (removed legacy init/embed commands, full transition to plan/apply) | ✅ Complete | [Review](../releases-archive/release-v0.72.0-review.md) |
| **v0.71.0** | 2025-06-25 | MVP | Module manifests & config mutability (Plan/Apply system complete) | ✅ Complete | [Impl](../releases-archive/release-v0.71.0-implementation.md) |
| **v0.70.0** | 2025-12-19 | MVP | Existing project support (`status`, `plan --add`, `plan --reconfigure`) | ✅ Complete | [Impl](../releases-archive/release-v0.70.0-implementation.md) |
| **v0.69.0** | 2025-12-03 | MVP | State management and incremental applies | ✅ Complete | [Impl](../releases-archive/release-v0.69.0-implementation.md) |
| **v0.68.0** | 2025-12-01 | MVP | Plan/Apply system core commands (Terraform-style declarative workflow) | ✅ Complete | [Impl](../releases-archive/release-v0.68.0-implementation.md) |
| **v0.67.0** | 2025-11-29 | MVP | Listings module with `AbstractListing` base model for verticals | ✅ Complete | [Impl](../releases-archive/release-v0.67.0-implementation.md) |
| **v0.66.0** | 2025-11-24 | MVP | Blog module with Markdown, featured images, and RSS feeds | ✅ Complete | [Impl](../releases-archive/release-v0.66.0-implementation.md) |
| **v0.65.0** | 2025-11-03 | MVP | Enhanced auth module and development tooling | ✅ Complete | No archived release doc |
| **v0.64.0** | 2025-11-01 | MVP | Theme rename to `showcase_*` (breaking change) | ✅ Complete | [Impl](../releases-archive/release-v0.64.0-implementation.md) |
| **v0.63.0** | 2025-10-29 | MVP | Authentication module with `django-allauth` and interactive embed | ✅ Complete | [Impl](../releases-archive/release-v0.63.0-implementation.md) |
| **v0.62.0** | 2025-10-25 | MVP | Split Branch infrastructure (module management CLI commands, GitHub Actions automation) | ✅ Complete | [Impl](../releases-archive/release-v0.62.0-implementation.md) |
| **v0.61.0** | 2025-10-24 | MVP | Theme system foundation (`--theme` flag, theme abstraction layer, HTML theme) | ✅ Complete | [Impl](../releases-archive/release-v0.61.0-implementation.md) |
| **v0.60.0** | 2025-10-19 | MVP | Railway deployment support (`quickscale deploy railway`) | ✅ Complete | [Impl](../releases-archive/release-v0.60.0-implementation.md) |
| **v0.59.0** | 2025-10-18 | MVP | CLI development commands (Docker/Django operation wrappers) | ✅ Complete | [Impl](../releases-archive/release-v0.59.0-implementation.md) |
| **v0.58.0** | 2025-10-18 | MVP | Comprehensive E2E testing infrastructure with Playwright and PostgreSQL | ✅ Complete | [Impl](../releases-archive/release-v0.58.0-implementation.md) |
| **v0.57.0** | 2025-10-15 | MVP | MVP launch: production-ready personal toolkit | ✅ Complete | [Impl](../releases-archive/release-v0.57.0-implementation.md) |
| **v0.56.0** | 2025-10-13 | MVP | Quality, testing, and CI/CD | ✅ Complete | [Impl](../releases-archive/release-v0.56.0-implementation.md) |
| **v0.55.0** | 2025-10-13 | Foundation | CLI implementation | ✅ Complete | [Impl](../releases-archive/release-v0.55.0-implementation.md) |
| **v0.54.0** | 2025-10-13 | Foundation | Project generator | ✅ Complete | [Impl](../releases-archive/release-v0.54.0-implementation.md) |
| **v0.53.3** | 2025-10-12 | Foundation | Project metadata and DevOps templates | ✅ Complete | [Impl](../releases-archive/release-v0.53.3-implementation.md) |
| **v0.53.2** | 2025-01-11 | Foundation | Templates and static files | ✅ Complete | [Impl](../releases-archive/release-v0.53.2-implementation.md) |
| **v0.53.1** | 2025-10-11 | Foundation | Core Django project templates | ✅ Complete | [Impl](../releases-archive/release-v0.53.1-implementation.md) |
| **v0.52.0** | 2025-10-08 | Foundation | Project foundation | ✅ Complete | [Impl](../releases-archive/release-v0.52.0-implementation.md) |

---

## Phase Summary

### Foundation Phase (v0.52.0 - v0.55.0)
**Dates**: See the release table above for the exact artifact dates recorded for each archived release.
**Focus**: Building incremental foundations before MVP

**Key Achievements**:
- Core utilities and scaffolding system
- Testing infrastructure
- CI/CD pipeline
- Docker & PostgreSQL setup
- Security best practices

### MVP Phase (v0.56.0 - v0.77.0)
**Dates**: This archive section covers archived MVP releases through the currently published records; see the table above for exact artifact dates.
**Focus**: Production-ready personal toolkit for client projects

**Key Milestones**:
- ✅ v0.56.0: MVP kickoff - personal toolkit strategy
- ✅ v0.60.0: CLI foundations (plan/apply concepts)
- ✅ v0.61.0: Module & theme architecture decision
- ✅ v0.63.0: Auth module with django-allauth
- ✅ v0.66.0: Blog & listings modules + real estate site
- ✅ v0.68.0: Plan/Apply system implementation
- ✅ v0.72.0: Complete Plan/Apply cleanup
- ✅ v0.76.0: Storage module with canonical public media URL contract
- ✅ v0.77.0: Backups module with private local/remote operational workflows and guarded restore paths

**Status**: Historical/archive view for completed MVP releases with published artifacts where available. For current MVP/Post-MVP boundaries and active release status, see [decisions.md](./decisions.md) and [roadmap.md](./roadmap.md).

### Post-MVP Phase (v0.78.0+)
**Dates**: Began with v0.78.0 on 2026-03-30; v0.79+ remains planned
**Focus**: Broader post-MVP expansion beyond the personal-toolkit scope, with community-platform capabilities remaining optional at v1.0.0+

**Key Milestones**:
- ✅ v0.78.0: Notifications module and post-MVP expansion-line kickoff

---

## Release Document Types

### Implementation Documents
**Purpose**: Detailed record of what was implemented, how it was tested, and validation results

**Typical Contents**:
- Task checklist (completed items)
- Implementation details
- Test results and validation
- Next steps

### Review Documents
**Purpose**: Quality assessment and approval status for a release

**Typical Contents**:
- Scope compliance check
- Code quality validation
- Testing review
- Approval status
- Recommendations

### Plan Documents
**Purpose**: Planning and design documents for releases requiring architectural decisions

**Typical Contents**:
- Problem statement
- Design options
- Chosen approach
- Implementation plan

---

## Accessing Historical Releases

### Via Git Tags
All releases are tagged in git:
```bash
git tag | grep v0.  # List all version tags
git show v0.72.0   # View specific release
```

### Via Release Documents
Full release documents are preserved in: [../releases-archive/](../releases-archive/)

### Via GitHub Releases
Production releases will be published to GitHub Releases (Post-MVP feature)

---

## Release Naming Convention

**Format**: `release-vX.XX.X-{type}.md`

**Types**:
- `implementation` - What was built and validated
- `review` - Quality assessment and approval
- `plan` - Design and planning (for architectural releases)

**Examples**:
- `release-v0.72.0-review.md`
- `release-v0.71.0-implementation.md`
- `release-v0.64.0-plan.md`

---

## Version Numbering Scheme

QuickScale uses semantic versioning with QuickScale-specific phase alignment:

**Format**: `v0.MINOR.PATCH`

**Phases**:
- `v0.52-v0.55`: Foundation Phase (incremental foundations)
- `v0.56-v0.77`: MVP Phase (personal toolkit)
- `v0.78-v0.99`: Post-MVP expansion phase (community-platform capabilities remain optional at v1.0.0+)
- `v1.0+`: Production-stable (long-term support)

**See**: [versioning.md](./versioning.md) for complete version scheme

---

## Future Release Management

Starting with **v0.73.0**, releases may use a mixed documentation layout:

1. **Planning**: Release tasks stay in [roadmap.md](./roadmap.md)
2. **Implementation**: Detailed maintainer-facing implementation/review notes go in [../releases-archive/](../releases-archive/) when created
3. **Summaries**: Concise reader-facing summaries may be published in [../releases/](../releases/)
4. **Completion**: Roadmap keeps the active checklist until a summary or archive artifact exists

**Benefit**: The roadmap stays actionable, recent summaries stay readable, and archival detail remains discoverable without promising files that do not yet exist

---

**Last Updated**: 2026-03-31
**Current Active Release Tracking**: [roadmap.md](./roadmap.md)
**Recent Summary Location**: [../releases/](../releases/)

---

## Detailed Release History

### v0.77.0: Backups Module - Archived Retrospective Record

**Status**: ✅ Archived retrospective implementation record

See [release-v0.77.0-implementation.md](../releases-archive/release-v0.77.0-implementation.md).

---

### v0.67.0: Listings Module — ✅ Complete

See [release-v0.67.0-implementation.md](../releases-archive/release-v0.67.0-implementation.md) for details.

---

### v0.68.0: Plan/Apply System — Core Commands

**Status**: ✅ Complete

See [release-v0.68.0-implementation.md](../releases-archive/release-v0.68.0-implementation.md) for details.

---

### v0.69.0: Plan/Apply System — State Management

**Status**: ✅ Complete

Terraform-style state management with incremental applies. See [release-v0.69.0-implementation.md](../releases-archive/release-v0.69.0-implementation.md).

---

### v0.70.0: Plan/Apply System - Existing Project Support

**Status**: ✅ Complete — 2025-12-19

See [release-v0.70.0-implementation.md](../releases-archive/release-v0.70.0-implementation.md).

---

### v0.71.0: Plan/Apply System - Module Manifests & Config Mutability

**Status**: ✅ Complete — 2025-06-25

See [release-v0.71.0-implementation.md](../releases-archive/release-v0.71.0-implementation.md) and [decisions.md: Module Manifest Architecture](./decisions.md#module-manifest-architecture).

---

### v0.72.0: Plan/Apply Functionality Cleanup

**Status**: ✅ Complete

See [release-v0.72.0-review.md](../releases-archive/release-v0.72.0-review.md).

---
