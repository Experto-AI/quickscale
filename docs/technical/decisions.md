# decisions.md

<!--
decisions.md — Authoritative Technical Policy Hub

WHAT THIS FILE IS: the repository-wide SSOT for rules, constraints, tie-breakers,
prohibitions, and technical document ownership. Every entry must be a statement
someone could *violate*.

WHAT BELONGS HERE: architectural decisions with their rationale; cross-cutting
implementation rules; explicit prohibitions; the document-ownership map.

WHAT DOES NOT: status reports and "current state" narrative (CHANGELOG.md);
workflow walkthroughs and examples (user_manual.md); timelines and open work
(roadmap.md); structure/spec detail owned by a narrow companion doc under
docs/technical/. If a statement can only become "out of date" rather than
"violated", it belongs in one of those.

TARGET AUDIENCE: Maintainers, core contributors, community package developers,
CI engineers.
-->

# Technical Decisions (Authoritative)

> **Related docs**: [Roadmap](roadmap.md) | [Glossary](../../GLOSSARY.md) | [Start Here](../../START_HERE.md)

**Purpose:** Repository-wide policy and tie-breaker hub for QuickScale architecture and development standards. Narrow companion docs under `docs/technical/` own the current implementation contract, validation policy, and structure references.

**Scope:** All first-party packages (core, CLI, themes, modules). Experto-AI and core contributors own these decisions.

**For what QuickScale currently ships** — CLI surface, feature matrix, runtime
pins, architecture boundaries — see
[implementation_contract.md](./implementation_contract.md). This file states the
rules that shipped surface must obey; it is not a description of it.

## Critical Rules

**Documentation Hierarchy:**
- ✅ decisions.md is authoritative and wins every conflict; [§ Document Responsibilities](#document-responsibilities) names the single owner of each other topic
- ✅ A change updates the owning document first, and decisions.md in the same change when policy, a tie-breaker or the ownership map changes
- ✅ Contributor engineering rules: `docs/contrib/rules.md`; stage guides: `docs/contrib/{plan,code,review,testing,debug}.md`
- ✅ `CHANGELOG.md` is the canonical release history index for all versions
- ✅ Release notes: `docs/releases/release-vX.XX.X.md` are the single public-facing release document for a version and may exist either as a clearly labeled release-prepared artifact before publish or as the linked note after tag/release publication
- ✅ Every public release note follows [publish_procedure.md §1.3.1](publish_procedure.md#131-release-note-format), including prepared artifacts awaiting manual publish
- ✅ Public release notes stay reader-facing and outcome-oriented; keep maintainer-only closeout detail in the release PR or active roadmap section instead of a second repository doc
- ✅ Unreleased or internal-only versions stay in `roadmap.md` and `CHANGELOG.md` until a maintainer intentionally prepares the single public release note for that version or publishes the tag/release
- ❌ Do not maintain separate implementation/review release docs or release-archive trees
- ❌ Never contradict decisions.md elsewhere

**Package README Policy:**
- ✅ First-party packages (`quickscale`, `quickscale_core`, `quickscale_cli`) MAY include a local `README.md`
- ✅ Package READMEs are informational context for package-specific installation and boundaries
- ✅ Root `README.md` and `docs/technical/decisions.md` remain authoritative when any wording differs
- ✅ `quickscale_modules/*` MUST have README.md (distributed as standalone)
- ❌ Never treat package README.md files as authoritative architecture, scope, or policy documents

## Architecture Decisions

### Module & Theme Architecture {#module-theme-architecture}

**Decision:** Modules and themes serve different purposes and use different
distribution mechanisms. Modules are ongoing runtime dependencies; themes are
one-time scaffolding.

<a id="integration-note-personal-toolkit-git-subtree"></a>
<a id="module-extraction-workflow"></a>

#### Modules — split-branch distribution

- ✅ Modules are developed on `main` in `quickscale_modules/`, published to mutable
  `splits/{module}-module` branches by the maintainer release tooling, sealed under
  identity-derived immutable version tags, and embedded by git subtree
- ✅ Users embed via `quickscale plan --add <module>` + `quickscale apply`, and
  update via `quickscale update`
- ✅ **The default embed path consumes the immutable
  `splits/<module>-module/<version>` tag — never a moving branch or the
  working tree.** Split branches are producer-side publication artifacts; the
  identity-derived tag is the released module ref. This is why release
  ordering is mandatory; see §[Module Version Lockstep](release_gates_policy.md#module-version-lockstep)
  Rule 3.
- ✅ **A split tag becomes permanent at PyPI publication, not at push.** Before the
  core release for that version is published, `splits/<module>-module/<version>`
  has no external consumer, so a wrong tag is corrected by deleting it and
  resealing rather than by burning a version number. Seal → test → fix → delete
  the affected tags → reseal, until the release converges. Once the core tag is
  pushed and PyPI has the packages the version is permanent, and a defect is
  corrected by a new version. See §[Module Version Lockstep](release_gates_policy.md#module-version-lockstep) Rule 4 for
  the correction procedure; the pre-publication loop is the intended way to
  converge, not a failure path.
- ✅ Modules are runtime dependencies (in `INSTALLED_APPS`), theme-agnostic, and
  backend-weighted; users can contribute improvements back via
  `quickscale push --module <name>`
- ❌ Modules are never tightly coupled to a theme

Workflow examples: [user_manual.md §4.3](./user_manual.md#43-planapply-commands).
Branch and generated-project layouts:
[repository_layout.md](./repository_layout.md) and
[generated_project_structure.md](./generated_project_structure.md).

#### Themes — generator templates

- ✅ `showcase_react` (React + TypeScript + shadcn/ui) is the **sole** supported
  and configured theme; the plan/apply CLI offers no other theme selection
- ✅ Themes are copied once at generation time (Jinja2 rendering); the user owns
  the generated code completely
- ✅ Any desired/state/recovery reference to `showcase_html` — or any other
  non-React theme — MUST fail closed before operational side effects
- ✅ Module releases MAY extend managed backend/runtime surfaces in existing
  projects, but newly scaffolded theme-owned routes, navigation, registries, and
  page source are guaranteed only on fresh generation or explicit manual adoption
- ❌ No embed/update path for themes — apply performs no automatic rewrite of
  user-owned files
- ❌ Vertical themes (CRM and similar) are not part of the shipped generator
  surface until a release note and this file explicitly add them

Theme-owned scaffolding that only fresh generations receive — the dormant PostHog
analytics helper and the Django-owned public `/social` and `/social/embeds`
entrypoints — is enumerated in
[generated_project_structure.md §React Starter Output](./generated_project_structure.md#react-starter-output).
Existing projects adopt equivalents manually; the backend-managed social transport
endpoints and settings wiring stay theme-agnostic.

The approved frontend stack (React 19+, TypeScript, Vite, pnpm, shadcn/ui,
Tailwind, React Router v7, TanStack Query, Zustand, React Hook Form + Zod,
Vitest, Playwright, ESLint + Prettier) is pinned in
[implementation_contract.md §Runtime Pins](./implementation_contract.md#runtime-pins-and-constraints).
Adding or swapping a frontend dependency requires a decision entry here.

#### Starter surface: billing and teams

- ✅ Generated starter output surfaces billing as a module flag only
  (`modules.billing`). Billing ships module-owned Django routes; QuickScale does
  not generate a starter-owned billing React page and does not rewrite existing
  project React files to adopt billing
- ✅ Billing SPA entry points (dashboard cards, sidebar navigation,
  `modulePaths.billing`, org-dashboard links) are restorable — restoring them is
  separate implementation work, not a blocked item
- ❌ Teams routes, flags, dashboard cards, and navigation stay excluded until
  teams ships as a valid public `quickscale plan` / `quickscale.yml` /
  `quickscale apply` selection

**Teams tie-breaker:** `teams` is not a shipped module and nothing is committed
— no timeline, no kickoff date, and no planning note in the repo.
Any [arch-audit.md](../others/arch-audit.md) finding whose horizon keys off "teams
kickoff" describes a condition that applies *if and when* teams is scheduled. Treat
every such finding as open-ended and deferred — not a roadmap item on a clock —
until a scheduling decision is recorded here. This rule is stated by trigger, not by
finding ID, so it survives audit regeneration.

#### Multi-org membership and org-switch

- ✅ Regular SaaS users belong to **exactly one** organization
- ✅ The server session (`ACTIVE_ORG_SESSION_KEY`) is the sole authority for org
  resolution for regular users
- ✅ VIEW-AS (superuser-only session override) is the sole path for operator
  org-scope debugging
- ❌ No org switcher in the user-facing UI
- ❌ No explicit-org API contract or session-sync endpoint — a client-side org
  parameter alongside a server-resolved session is a dual-authority defect

Future multi-org membership is not precluded, but requires revisiting this
decision and implementing the explicit-org API contract at that time.

Design detail: [organizations.md](./organizations.md). Isolation rules:
§[Multi-tenant SaaS Architecture](#multitenant-saas-architecture).

---

### Split-Facade Seams {#split-facade-seams}

**Rule:** A test's seam is the module that defines the name (or an injected collaborator),
never the re-export path. A private module (`_<name>.py`) imports the sibling modules that
define its collaborators and never imports a facade of its own distribution. A facade imports
its private siblings one way and re-exports public names only.

- ✅ `patch("<defining-module>.X")`; a private module resolves each collaborator at call time
  through the module that defines it, and a facade keeps its public import paths by
  re-exporting public names (`X as X`) from its private siblings.
- ❌ A `_<name>.py` module importing a facade of its own distribution — the CLI command and
  utility facades, `dr_engine`, and billing included; a private or incidental name in a
  facade's re-export block or in a facade-surface test's expected set.
- Enforcement: `scripts/check_split_facade_imports.py` (registered gate
  `check-split-facade-imports`) derives its scope from the layout — every package under a
  first-party distribution's `src/` tree carrying a `_*.py` module — and rejects a private
  module importing a facade module of its distribution, or a name that facade does not define
  itself; the CLI split facades (`quickscale_cli/tests/test_split_facade_surfaces.py`) and
  billing `services` (`test_services_facade_surface.py`) each carry a surface test that pins
  public names only.

---

### Frontend Rendering Decisions {#frontend-rendering-decisions-sa241}

**Decision 1 — Frontend split.** React is the standard frontend for new
application and public pages — including a public page whose crawlable first
response Django fills in (Decision 2), where the React surface owns the
interactive page. Django-rendered surfaces stay Django-rendered on
the shared design: `auth` and `billing` keep their Django pages, the
module-shipped Django pages (`blog`, `listings`, and the CRM dashboard) keep
theirs until an SA154 item promotes a React replacement, and Django admin stays
as shipped.

- ✅ A new application page, or a new public page, is built as a React surface
  in the theme and reaches the browser through the one `window.__QUICKSCALE__`
  seam or a DRF endpoint (§[Frontend Theme Source
  De-Specialization](#frontend-theme-despecialization-dormant-files)).
- ✅ A module-shipped Django page keeps its Django rendering and its existing
  module base and block contract; promoting it to React is an SA154 inventory
  item, not an incidental edit.
- ❌ Rewriting a module's shipped Django page as a React page outside an SA154
  promotion; a second frontend stack, a second seam, or a second design source.

**Decision 2 — Django fills the SPA document's head and a crawler summary for
public catalog and detail pages.** SA153's public catalog and detail pages stay
the project's React surface. When Django serves the SPA document for one of
those routes, it reads the same published, organization-scoped listing data the
JSON read API serves and writes into that document the page's title,
description, canonical link, Open Graph tags, and a plain-HTML summary of the
content inside the React root. A client that runs no JavaScript receives that
content; a browser mounts React as usual, which replaces the summary and fetches
from the API.

- ✅ The fill happens per request from the database, so a newly published or
  edited listing is correct in previews and crawls without a rebuild or deploy.
- ✅ `sitemap.xml` and `robots.txt` are Django views over the published
  listings, never a hand-maintained list or a build artifact.
- ✅ The JSON read API remains the React layer's data contract; the summary is
  a fallback, not a second UI, and carries no interactive behavior.
- ✅ The SPA document and the `window.__QUICKSCALE__` seam keep their shape; the
  browser boot mounts with `createRoot`, with no hydration or dehydrated state.
- ❌ A build-time or runtime React render (Vite SSR, a Node process, or a
  headless browser); a committed content snapshot; Django-rendered property
  pages that replace the React surface; a crawler-only document chosen by
  user-agent detection.

**Options considered for Decision 2:**

| Option | Why not chosen |
|---|---|
| Prerender the React pages with Vite SSR in the image build | The build has no database, so documents and the sitemap come from a committed snapshot and stay stale until someone re-exports, commits, and redeploys; it also widens the theme seam with route and dehydrated state |
| Runtime React SSR in a Node renderer | Adds a Node runtime and service to a Python-only, single-service deployment and a second data path |
| On-demand headless-browser prerender (Playwright plus a cache) | A browser runtime in production plus cache invalidation; fragile |
| Django-rendered property pages | Replaces the React public surface SA153 delivers |
| Django fills the SPA document's head and a crawler summary (chosen) | Live data, no new runtime or build step, no seam change; the React page is unchanged |

**Related docs:** [frontend.md](frontend.md) | [roadmap.md](./roadmap.md)

---

## Authoritative Policies

**Settings Inheritance:**
- ✅ Current generated projects: Standalone `settings.py` (no automatic inheritance from quickscale_core)
- ✅ Generated settings import the versioned `quickscale_core.runtime.settings` facade for executable runtime contracts — a library import, not settings inheritance
- ✅ Optional: Manual inheritance after git subtree embed (advanced users)
- ❌ NO automatic settings inheritance in generated projects

**Packaging (All QuickScale Packages):**
- ✅ Poetry package manager
- ✅ Root-level pyproject.toml + poetry.lock (required); per-module `poetry.lock` files are not supported (monorepo root is the single resolution source)
- ✅ src/ layout (prevents accidental imports)
- ✅ Use ./scripts/install_global.sh for Poetry-built user installs
- ❌ NO requirements.txt generation
- ❌ NO setup.py files
- ❌ NO direct system-Python pip install flows (`pip install --user`, `--break-system-packages`, etc.)

**Development Tools:**
- ✅ Ruff: Format + lint (replaces Black + Flake8)
- ✅ MyPy: Type checking (strict mode)
- ✅ pytest + pytest-django: Testing
- ✅ pytest-cov: Coverage reporting
- ❌ NO Black (use Ruff format)
- ❌ NO Flake8 (use Ruff check)

**Database Policy (Breaking):**
- ✅ PostgreSQL-only — dev, CI testing, and production; no exceptions
- ✅ `DATABASE_URL` is required for local DB configuration
- ❌ SQLite is prohibited for any purpose, **including test databases** — `django.db.backends.sqlite3` in any `tests/settings.py` is a policy violation
- ❌ `skipif(not postgres)` / `QUICKSCALE_TEST_DB` env-var guards on isolation tests are prohibited — isolation tests must run against PostgreSQL unconditionally; a job that cannot provision Postgres is misconfigured, not a valid reason to skip
- ❌ No backward compatibility layer, migration shim, or fallback mode for SQLite-based setups

**Validation and Automation Entry Points:** See [validation_policy.md](./validation_policy.md#repository-command-reference) for the authoritative repository command baseline and assistant guidance, and [§Validation Tiers](./validation_policy.md#validation-tiers) for which of those commands a given change owes.

**Security gate tooling:**
- ✅ Dependency vulnerability scanning uses Trivy v0.74.0 against the single
  committed root Poetry lockfile (which resolves core, CLI, and modules through
  path dependencies), including development dependencies
- ✅ Static security analysis uses Bandit 1.9.4 over maintained first-party Python
  source with the focused category contract and reviewed suppression ledger
- ✅ Native Trivy acquisition supports Linux x86_64/arm64 and macOS
  x86_64/arm64; Windows contributors use WSL. Every release asset is bound to
  the official v0.74.0 manifest SHA-256 before safe extraction
- ❌ A missing tool, unsupported native host, stale vulnerability database,
  checksum mismatch, unsafe archive, or malformed scanner result must fail the
  gate; security checks never silently skip

### Module-Specific Architecture Decisions {#module-specific-architecture}

#### Blog Module — Custom Django Implementation

**Decision:** The blog module is a custom Django implementation, not a wrapper
around an existing blogging package.

**Rejected (do not re-introduce):**
- ❌ **Wagtail** — a full CMS with 50+ dependencies; contradicts QuickScale's lightweight philosophy
- ❌ **django-blog-zinnia** — unmaintained (last release 2016), incompatible with Django 4.x+
- ❌ **Puput** — Wagtail-based, so it inherits Wagtail's complexity

**Scope boundary:** comments, advanced SEO (Open Graph, JSON-LD), related-posts
algorithms, and scheduled publishing are deliberately **out of scope** — users
reach for a third party (Disqus/Commento, django-celery-beat). Adding any of them
to the module requires a decision entry here.

---

#### Disaster Recovery Engine Boundary Contract {#disaster-recovery-engine-boundary-contract-f5--m10}

**Rule:** Platform-level backup/restore orchestration lives in a centrally owned DR engine; the
embeddable `backups` module keeps only thin Django-facing surfaces, reached through a typed adapter.

**Target ownership split:**

1. **Centrally owned DR engine (CLI/core layer)** — owns all platform-level
   orchestration:
   - Snapshot and archive primitives (database custom-dump capture, archive
     packaging).
   - Restore and orchestration flow (validation, ordered execution sequencing,
     destructive-operation gating).
   - Verification logic and verification-record assembly.
   - Rollback-pin lifecycle and pin handling.
   - Sidecar payload assembly (environment-variable manifests, release metadata,
     verification records).
   - Remote-storage orchestration.
   - Route/environment resolution and cross-route promotion sequencing.

2. **Embeddable `backups` module (thin Django-facing surfaces)** — owns only what
   genuinely requires Django/project context:
   - ORM models `BackupArtifact` and `BackupPolicy` (project-local DR records) and
     their migrations.
   - Admin UI for those models, including the guarded local-file restore surface.
   - A thin, explicitly documented Django adapter that exposes project-bound
     capabilities the engine needs (database connection/settings, `MEDIA_ROOT`,
     app/settings introspection).
   - No platform-level orchestration logic.

**Boundary interface:**
- The engine MUST NOT be reached through implicit management-command +
  environment-variable + stdout-JSON coupling. Replace it with an explicit
  internal boundary:
  - **Typed requests** (snapshot, restore — carrying an explicit destructive-op
    flag —, media-sync, verification) instead of environment-variable passing.
  - **Typed results** (snapshot descriptor, per-surface results, sidecar
    payloads, rollback pin) instead of parsing stdout JSON.
  - The embeddable module exposes a single documented adapter that the engine
    calls for project-bound operations. Management commands, if retained, become
    thin wrappers over this boundary rather than the protocol itself.
- Destructive restore stays gated; the gate becomes an explicit parameter on the
  restore request rather than the `QUICKSCALE_BACKUPS_ALLOW_RESTORE` env var.

**Invariants preserved across the split:**
- The Backups contract rule (above) remains authoritative: PostgreSQL 18 native
  custom dumps as the real restore path, JSON artifacts export-only, private
  operational artifacts, credentials referenced by environment-variable name only,
  and guarded destructive restore across both supported surfaces.
- No change to the user-facing `quickscale dr {capture,plan,execute,report}` CLI
  surface.
- The protocol replacement is a maintainer-internal boundary and needs no
  backward-compatibility shim. Generated-project dependency resolution is
  documented in the backups module README.

---

## Document Responsibilities

This is the only document-ownership map. Every fact has one owner, and other documents link to
the owner instead of restating it. **A** = authoritative: rules are binding and are written as
MUST / MUST NOT (enforced by `quickscale_core/tests/test_doc_phrasing.py`).

| Document | Owns | |
|---|---|---|
| decisions.md | repo-wide policy, tie-breakers, prohibitions, this map | **A** |
| implementation_contract.md | shipped contract, feature matrix, CLI surface | **A** |
| module_architecture.md | plan/apply state rules, module config, manifest, derivation, wiring, implementation requirements, inventory and presence states | **A** |
| module_conventions.md | numbered module conventions (rules 1–50) | **A** |
| release_gates_policy.md | module version lockstep, gate coverage and budget, quality and file-size thresholds | **A** |
| validation_policy.md | validation entrypoints and tiers, candidate integration, coverage, E2E | **A** |
| generated_project_structure.md | generated-project layout, artifact placement, generation guardrails | **A** |
| repository_layout.md | maintainer-repo layout, naming/import matrix | **A** |
| module-extension.md | module extension contract, module-authoring checklist | **A** |
| generated_file_ownership.md | beta-migration generated-file ownership rules and `INTENTIONALLY_UNMANAGED` inventory | **A** |
| publish_procedure.md | pre-publish gate, ordered release phases, release-note format | **A** |
| ai_hydration_topology.md | `adaptive.rules.md` include graph and its change rules | **A** |
| GLOSSARY.md | terminology | **A** |
| docs/contrib/rules.md | contributor engineering rules | **A** |
| plan-apply-system.md | plan/apply schemas, state, execution order | |
| quality_tools.md | quality analyzers, threshold gate spec | |
| versioning.md | `VERSION` single source and propagation | |
| user_manual.md | CLI workflows and worked examples | |
| roadmap.md | open work; its scheduling table is canonical for tracks, dependencies, next actions. Completed work moves to CHANGELOG.md | |
| CHANGELOG.md | release history, one entry per version | |
| docs/releases/ | one public note per version | |
| docs/others/*-audit.md | open findings only; finding numbers are pass-local and MUST NOT be cited elsewhere | |
| ai_context.md | derived AI baseline; on conflict the owner above wins | |
| README.md | overview, quick start, package table; wins over package READMEs | |
| START_HERE.md, docs/index.md | navigation | |
| package and module README.md | package-local install and surface; never contradicts an **A** doc | |

**Rule:** Update the narrow owner first when changing its slice. Update decisions.md in the same change when the repository-wide ownership map, policy, or tie-breakers change.

Other documents link to the roadmap scheduling table instead of repeating queue
counts, lane readiness, or dependency prose. Consistency tests validate structural
contracts such as task coverage, legal tracks, and valid dependencies; they must
not hardcode current-status narrative wording. Keep durable execution rules in
[validation_policy.md](validation_policy.md#candidate-review-and-integration),
and historical reviews and scheduling decisions in CHANGELOG.md.

### Release scope safeguards

- ❌ `quickscale_devtools` in the public publish package list; it is maintainer-internal.
- ✅ A watchlist finding is acted on only when its trigger fires, or by an explicitly scoped,
  trigger-independent ticket.
- ✅ New scope requires its own ticket; it never expands an existing delivery.

## Unit/Integration Gate Split

**Rule:** The test suite is split into two independent gates — a DB-free unit gate
and a PostgreSQL 18 integration gate.

- ✅ The unit gate (`make test-unit`) covers core + CLI only and requires no
  PostgreSQL and no special database role
- ✅ The integration gate (`make test-integration`) runs module suites against a
  restricted `NOBYPASSRLS NOSUPERUSER` role, in both `ci.yml` and `publish.yml`,
  with the RLS boot guard active — that restricted role *is* the tenant-isolation
  coverage
- ✅ `QUICKSCALE_ALLOW_BYPASSRLS=1` is set explicitly per-suite by a developer when
  a BYPASSRLS-dependent test needs it
- ✅ Known restricted-role failures are quarantined **individually against a
  ticket**; quarantined entries are excluded from the exit code and coverage mean
- ❌ No blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export on the unit path
- ❌ Non-quarantined module-suite regressions never pass the gate

Gate scopes, make targets, and role grants:
[validation_policy.md §Testing Standards](./validation_policy.md#testing-standards).
Which gate a given change owes is decided by tier, not by habit:
[validation_policy.md §Validation Tiers](./validation_policy.md#validation-tiers).

## Operational Decisions

**Core Principles:**
- ✅ Starting points over complete solutions (customize for business needs)
- ✅ Creation-time assembly (NO runtime dynamic loading)
- ✅ Standard Django architecture (app_label namespacing, standard migrations)
- ✅ Separate CLI package (independent release cadence from core)
- ✅ src/ layout (prevents import errors during testing/building)
- ✅ Direct imports (NO DI frameworks or service registries)
- ✅ Single providers at the product policy layer (Stripe payments, Resend email)
- ✅ Django email delivery for notifications uses `django-anymail` as the approved delivery layer with Resend as the current first-class provider
- ✅ Version pinning (predictable compatibility for Django foundations)
- ✅ **Fail hard** — every configuration error, missing dependency, and invalid runtime state raises an explicit exception; no silent fallbacks, no graceful degradation (see §fail-hard-principle below)

---

### Launcher One-Shot Command-Env Contract {#launcher-one-shot-command-env-contract}

**Rule:** Generated project startup scripts
and settings use two mutually exclusive one-shot environment variables to
select the database connection and bootstrap mode. These variables are always
set as inline command prefixes — never as persistent environment configuration.

**Design:**

1. **``QUICKSCALE_PRIVILEGED_COMMAND``** — Privileged DB operations that
   require the superuser ``DATABASE_URL`` (``migrate`` and
   ``createcachetable``).
   The launcher sets this as an inline prefix *and* blanks
   ``RUNTIME_DATABASE_URL=""`` so the superuser role is used for schema
   changes (the runtime role has ``NOSUPERUSER``/``NOBYPASSRLS`` and cannot
   run DDL).

2. **``QUICKSCALE_NON_DB_COMMAND``** — DB-free bootstrap operations
   (``collectstatic``, ``compilemessages``) that do not need a live
   ``DATABASE_URL``. ``production.py`` supplies a dummy ``postgresql://``
   URL when ``DATABASE_URL`` is unset, keeping the process importable
   without a real database connection.

**Rules:**

- ✅ Both variables are one-shot inline prefixes only (e.g.,
  ``QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" python manage.py migrate``).
  They are never exported, never set in ``.env``, never written to
  ``docker-compose.yml`` ``environment:`` blocks, never documented as
  persistent configuration, and never checked into version control.
- ✅ They are mutually exclusive — the ``production.py`` seam raises
  ``ValueError`` if both are set simultaneously.
- ✅ ``QUICKSCALE_PRIVILEGED_COMMAND`` requires ``RUNTIME_DATABASE_URL=""``
  (explicitly blank); omitting it raises ``ValueError``.
- ✅ ``QUICKSCALE_NON_DB_COMMAND`` does not require a real ``DATABASE_URL``;
  a dummy URL is substituted when ``DATABASE_URL`` is absent.
- ✅ The default serving path (neither command var set) uses
  ``RUNTIME_DATABASE_URL`` when present, or raises ``ValueError`` (fail-closed).

**Implementation surface:**

| Variable | Values | Set by | Connection selected |
|---|---|---|---|
| ``QUICKSCALE_PRIVILEGED_COMMAND`` | ``migrate``, ``createcachetable`` | ``start.sh`` / ``quickscale manage`` (inline prefix) | ``DATABASE_URL`` (superuser) |
| ``QUICKSCALE_NON_DB_COMMAND`` | ``collectstatic``, ``compilemessages`` | ``Dockerfile`` build step (inline prefix) | Dummy ``postgresql://`` URL |

The sanctioned privileged set is exactly the two Django built-ins above. Each of
the four enforcing stations keeps an independent fail-closed refusal, and a
cross-station regression test requires their declarations to agree.

**Related:** [Fail-Hard Principle](#fail-hard-principle) (the mutual-exclusion
check and missing-arg validation follow fail-hard); [Multi-tenant SaaS
§RLS enforcement rule](#multitenant-saas-architecture) (the runtime role's
``NOSUPERUSER``/``NOBYPASSRLS`` is the reason privileged commands need the
superuser ``DATABASE_URL``).

---

### Runtime Settings Facade (Public API) {#runtime-settings-facade}

**Rule:** `quickscale_core.runtime.settings` is the public import
path for the executable runtime contracts shared by generated settings and
launchers. It exports the client-identity and correlation-id middleware, the
trusted-proxy derivation, the DRF composition, the
privileged-command/runtime-database selection, the production SECRET_KEY guard,
and the structured-logging helpers.

**Why:** generated settings are user-owned and never upgraded; one facade ships every contract fix through the `quickscale-core` lockstep pin.

**Rules:**
- ✅ Generated `settings/base.py` and `settings/production.py` import the
  facade and keep only user configuration: `base.py` composes `REST_FRAMEWORK`
  through `compose_rest_framework()` instead of declaring DRF defaults inline.
- ✅ Every generated project declares the bounded `quickscale-core` lockstep
  pin (`>=X.Y.0,<X.(Y+1).0`) in its `pyproject.toml`, including zero-module
  projects.
- ✅ The privileged-command contract test holds the facade's
  `KNOWN_PRIVILEGED_COMMANDS` declaration in place of the retired template
  copy.
- ✅ The beta-migration tool checks that effective settings select their
  database through `resolve_runtime_database_url`: it rewrites a recognized
  pre-facade block onto the facade and refuses an unrecognized inline copy of
  the contract.
- ❌ No generated settings module re-declares the contract inline.

**Adoption:** existing projects adopt the facade through the declared
generated-project contract step (SA207).

---

### ImproperlyConfigured Exception Identity {#improperlyconfigured-exception-identity}

**Decision:** QuickScale's shared contract layer
(``quickscale_core.contracts``) defines its own
:class:`~quickscale_core.contracts.module_discovery.ImproperlyConfigured`
exception, decoupled from Django's ``django.core.exceptions.ImproperlyConfigured``.

Two same-named ``ImproperlyConfigured`` classes coexist — one in the contracts
layer and one in Django's module-runtime layer. Catchers and raisers must choose
the correct import:

- **Contracts-layer catchers** (code in ``quickscale_core.contracts`` or
  code that catches exceptions from contract-layer APIs) import
  ``quickscale_core.contracts.module_discovery.ImproperlyConfigured``.
- **Django-runtime catchers** (generated-project settings, module
  ``AppConfig.ready()`` code, standard Django startup paths) import
  ``django.core.exceptions.ImproperlyConfigured``.

Importing the wrong class will silently fail to catch the intended exception,
causing an unhandled crash instead of graceful handling. This is a documented
identity-split — not a refactoring opportunity to consolidate into one shared
alias.

---

### Fail-Hard Principle {#fail-hard-principle}

**Rule:** Every configuration error, missing required dependency, or invalid runtime state must raise an explicit, descriptive exception immediately. Silent fallbacks, best-effort defaults, and graceful degradation are prohibited in the generator, CLI, and manifest stack.

**What this means concretely:**
- ✅ Raise `ImproperlyConfigured`, `ValueError`, `RuntimeError`, or `SystemExit` on invalid config — never substitute a default
- ✅ Raise immediately when a required adapter, path, or resource cannot be located — do not attempt to continue with a substitute
- ✅ Surface the root cause in the error message so the operator knows exactly what to fix
- ✅ Fail at startup / import time — not at first use — so configuration problems are visible immediately
- ❌ No `except Exception: pass` or `except ImportError: pass` in configuration, setup, or discovery paths
- ❌ No "best-effort defaults" when a required path or resource cannot be found
- ❌ No silent fallback chains (try A → try B → silently return something)
- ❌ No backward-compat shims or read-through legacy imports, unless explicitly documented below with a bounded exception and a sunset plan

**Scope:** Applies to the generator/CLI setup, manifest adapter resolution, module discovery, configuration loading, and Django app startup. Does **not** apply to domain logic inside generated projects (which are user-owned code) or to DR recovery orchestration (which is intentionally error-recovery context — fallback artifacts and remote restoration are by design).

**Global constraint that reinforces this:** No existing users, no migration path, no backward compatibility — every change is a clean break. The fail-hard principle is the runtime expression of this constraint: if something is misconfigured it must be fixed, not silently worked around.

**Documented exceptions** (each requires explicit justification in the code comment, a `# F-EXCEPTION: <tag>` label, and removal when the condition no longer applies):

| Tag | Location | Justification | Sunset |
|-----|----------|---------------|--------|
| F12.2 | `project_state.py:_read_through_import_legacy()` and `materialize_authoritative_state()`; `remove_command.py:_load_legacy_tracking()` and `_record_mutation_snapshots()` (legacy `config.yml` / `file_hashes.yml` compatibility paths) | One-time compatibility window: projects predating the consolidated `state.yml` format may still depend on legacy `config.yml` / `file_hashes.yml` data while consolidated `state.yml` becomes authoritative. `project_state.py` logs-and-skips stale legacy import failures so consolidation is not blocked; `remove_command.py` still consults and snapshots legacy `config.yml` so rollback-safe module removal can preserve compatibility tracking during the same sunset window. Does NOT cover `_load_managed_file_records_for_drift()` — its legacy `file_hashes.yml` fallback is a drift-detection design choice, not a compatibility path. | Remove once the consolidated state format has been deployed for two full releases with no known pre-consolidation projects in active use. |

**Known violations:** tracked in [tech-audit.md](../others/tech-audit.md), the SSOT for found-not-yet-fixed fail-hard violations. Remediated findings are dropped from that file and closed out in CHANGELOG.md.

---

### JSON API Endpoint Base Contract {#json-api-endpoint-base-contract}

**Rule:** Every authed, state-changing JSON endpoint subclasses one of exactly two sanctioned bases. There is no third permanent option.

- ✅ **DRF baseline** (`rest_framework.views.APIView` with core's `QuickscaleSessionAuthentication` for automated CSRF enforcement; permission class per endpoint) — the default for any new JSON endpoint that does not need organization-role scoping. `IsAuthenticated` is the default for endpoints where all requests require an authenticated user; `AllowAny` marks only an explicitly public endpoint, and a view that needs the caller authenticated (or holding an organization role) declares that in `permission_classes`, never `AllowAny` plus a hand-written check (rule 19). Used by billing, CRM, and forms.
- ✅ **`OrgApiBaseView`** — for endpoints that need organization-role/membership scoping specifically. Chosen as a second sanctioned base rather than reimplementing org-role checks as a DRF permission class, because that logic is tenant-isolation-adjacent (see §multitenant-saas-architecture) and rewriting working, tested code for stylistic consistency alone carries regression risk for no user-visible benefit.
- ❌ A plain-`View` + `@csrf_exempt` + manual `_enforce_csrf()` idiom is not a third sanctioned option and is not grandfathered as legacy — this project removes workarounds rather than permanently tolerating them alongside the sanctioned shape.
- ✅ **Signature-verified webhooks** (Stripe, etc.) are a different trust class, exempt from this rule's authentication and CSRF requirements — the calling party cannot present a CSRF token. They are DRF `APIView`s without authentication, permission, or throttle classes (Module Conventions rule 26), which DRF does not CSRF-check; the signature is their authentication, rule 9's handler renders their errors, and the pairing gate (`scripts/check_csrf_exempt_gate.py`) carries no webhook helper.

**SA215's change to this section has landed** (§[Module Conventions](module_conventions.md#module-conventions) rule 9):
`OrgApiBaseView` is a DRF `APIView`, so both bases are DRF views and the plain-`View` idiom is
gone from modules. The blog module's function-view exception below is retired: both blog API
endpoints are DRF views with session authentication only, and `BLOG_API_TOKENS` is removed.

**Retired exception — blog dual-auth function views:** the blog module's `upload_media_api` and
`publish_post_api` were function views paired with `authenticate_blog_api_request()` for
session-or-Bearer-token authentication. Both are now DRF views with session authentication only,
and `BLOG_API_TOKENS` is removed; the CSRF CI gate (`scripts/check_csrf_exempt_gate.py`) no longer
recognizes the retired helper. No new function-view endpoints may use this exception without
explicit approval.

The CSRF CI gate continues to enforce the pairing requirement across all `csrf_exempt` callsites.

**Related docs:** [roadmap.md](./roadmap.md) | [arch-audit.md](../others/arch-audit.md)

---

### Notifications Contract

- Authoritative notifications configuration lives in `quickscale.yml`, generated Django settings, and environment variables. Any `NotificationSettings` admin surface is a read-only operational snapshot only, with no secrets and no alternate mutable config path.
- `modules.notifications.sender_email` defaults to `noreply@example.com` as a local-development placeholder only.
- When `modules.notifications.resend_domain` is set, `quickscale apply` requires a non-placeholder sender email plus a valid `modules.notifications.resend_api_key_env_var` reference; apply fails hard instead of silently leaving live delivery on the console backend.
- Runtime backend selection stays on Django's console email backend until live Resend delivery is fully configured. If the live Resend backend is active anyway and the placeholder sender or resolved API key is still missing, queued deliveries fail explicitly rather than degrading silently.
- Delivery tracking is recipient-granular. A multi-recipient send fans out into one tracked provider send/message ID per recipient delivery record.
- Provider-visible tags/metadata are optional and limited to a tiny non-sensitive allowlist. Internal correlation identifiers stay local to QuickScale-owned records.

**Provider choice.** Resend is the only first-class sender, delivered through Django Anymail
on the standard Django email path, with app-owned templates and an app-owned dispatch record.
Direct Resend API integration is rejected (weaker portability, more provider code). Fallbacks,
in order, if inbound email becomes required or cost-at-scale dominates: Postmark, then Amazon SES.

### Analytics Provider {#analytics-provider}

PostHog is the only approved analytics provider: zero cost floor, an official Django SDK,
SPA fit, and server-side capture. Settings are flat, and the backend exposes service-style
helpers. Existing projects adopt the frontend manually. Fallbacks, in order, if the free tier
disappears or a privacy-first/EU-only default becomes policy: Plausible, then Matomo
(self-hosted). Umami, Fathom and GA4 are not approved.

### Multi-tenant SaaS Architecture {#multitenant-saas-architecture}

**Architectural Decision:** QuickScale-generated SaaS apps use **PostgreSQL FORCE RLS on a single Railway deployment** — one app service + one PostgreSQL 18 service, all tenants share one database and schema. Organizations are the billing and isolation unit. See [organizations.md](./organizations.md) for the full design and [roadmap.md](./roadmap.md) for open implementation work.

**Chosen shape:**
- ✅ Single Railway project (one app + one PostgreSQL 18 service); Railway bill is flat regardless of tenant count
- ✅ Shared database + shared schema; isolation enforced by PostgreSQL FORCE RLS on the 22 shipped ENROLLED models (CRM 7, Forms 4, Billing 4, Blog 4, Listings 1, Social 2) plus ContextVar-driven `TenantManager` scoping — runtime membership is derived from model markers
- ✅ Billing unit: `Subscription → Organization` (not per-user)
- ✅ URL routing: flat routes only — `/crm/`, `/blog/`; no `/orgs/<slug>/` content routes
- ✅ Regular users belong to exactly one organization; no org switcher in the user-facing UI (see §[Module & Theme Architecture](#module-theme-architecture) → Multi-org membership)
- ✅ Module access is differentiated by credits plus ORM-backed `Plan.features` gates

**RLS enforcement rule (critical):**
- RLS enforces only when the app connects as the restricted `NOSUPERUSER/NOBYPASSRLS` runtime role selected by `RUNTIME_DATABASE_URL`
- Generated runtime serving now fails closed when `RUNTIME_DATABASE_URL` is unset; only the named privileged command paths intentionally use the superuser `DATABASE_URL`
- **Always-on boot guard:** `orgs.QuickscaleOrgsConfig.ready()` asserts `rolbypassrls=false AND rolsuper=false` on every boot where `QUICKSCALE_PRIVILEGED_COMMAND` is unset or set to an unrecognised value — regardless of `QUICKSCALE_ORGS_MODE` or `DEBUG`. Raises `ImproperlyConfigured` if the connected role has BYPASSRLS and/or SUPERUSER unless one of the two explicit exemptions applies:
  1. `QUICKSCALE_PRIVILEGED_COMMAND` set to a sanctioned privileged DB command (`migrate` or `createcachetable`) — the deployment `start.sh` and `quickscale manage` unset `RUNTIME_DATABASE_URL` so these operations run under the superuser role (correct and deliberate). The two-command contract is independently declared by the `orgs` module guard (`_PRIVILEGED_COMMANDS` in `checks.py`), the `quickscale_core.runtime.settings` facade, the CLI producer, and the generated `start.sh` launcher; none is a single source of truth, and all four must remain fail-closed and aligned.
  2. `QUICKSCALE_ALLOW_BYPASSRLS=1` — non-serving environment-variable escape hatch for intentional single-tenant/development use. It is never a production serving mode.
- `start.sh` deliberately unsets `RUNTIME_DATABASE_URL` for `migrate` and `createcachetable`; supplied argv exits 2 without a privileged path; `runserver`/`gunicorn` must still use the restricted runtime role
- `quickscale manage` clears `RUNTIME_DATABASE_URL` only for those two sanctioned commands; every other management command (for example `createsuperuser`) runs under the restricted runtime role, which the boot guard requires
- Runtime-role provisioning is not a third privileged Django command: when `RUNTIME_DB_PASSWORD` is set (as `quickscale deploy railway` does), `start.sh` creates or updates the `NOSUPERUSER/NOBYPASSRLS` role with a direct superuser `DATABASE_URL` connection *before* Django boots, so the guard and the two-command contract are untouched. It refuses a role that is the superuser login or an existing superuser

**Isolation architecture rules (permanent):**

- Runtime tenant classification and membership: `is_classified_in_registry()` classifies installed concrete project models from explicit ``tenant_excluded`` markers, ``TenantModel`` inheritance, and implicit M2M-through inference. `is_tenant_model()` and `get_tenant_models()` derive only the positively enrolled tenant-model set from ``TenantModel`` inheritance; ``tenant_excluded`` wins over every enrollment signal, and a ``TenantManager`` on a model that does not inherit ``TenantModel`` fails startup through orgs' ``checks.py`` (Module Conventions rule 13). Classification and FORCE-RLS refresh must not fall back to or consult the literal ``TENANT_TABLE_REGISTRY``. The literal remains only a shipped-module CI parity oracle and is test-owned (Module Conventions rule 34 keeps it out of shipped source). Its 22 shipped ENROLLED models (CRM 7, Forms 4, Billing 4, Blog 4, Listings 1, Social 2) each carry a direct ``organization_id``, inherit the ``objects`` / ``all_objects`` ``TenantManager`` pair from ``TenantModel``, and ship the exact two-policy FORCE-RLS contract rendered by ``apply_force_rls``.
- Project-owned tenant extensions: a concrete model in an installed project app may join the runtime tenant set by inheriting ``TenantModel`` (directly or through a module's abstract base) without a shipped-registry entry or vendored-module edit. Its initial migration owns the table and calls ``apply_force_rls`` to install exactly one tenant-only ``FOR ALL`` base policy plus its ``<base>_select`` operator-read ``FOR SELECT`` policy. Both policies are permissive and apply to ``PUBLIC``; the base policy has identical current-organization ``USING`` and ``WITH CHECK`` predicates, while the select policy has the rendered current-organization-or-operator ``USING`` predicate and no ``WITH CHECK``. Runtime refresh resolves each existing table's unique base policy from ``pg_policies`` before any DDL; missing or ambiguous policy metadata fails before mutation. The base name remains migration-owned rather than inferred from model metadata, but the companion must be named ``<base>_select``. The isolation checks reject a missing, extra, misnamed companion, restrictive, role-limited, or predicate-weakened policy.
- Child tables: every tenant-owned child/detail table must denormalize `organization_id` directly onto the row and use a direct FORCE-RLS policy referencing that column; parent-join RLS policies are not used. This is the project default for all future tables.
- Ambient scoping: request-scoped tenant reads flow through `request.org` → ContextVar (`app.current_org_id`) → `TenantManager`; the authoritative tenant-facing API is ambient manager scoping, not `.for_org(...)` query chaining.
- Operator access: request paths use `operator_access(user=..., reason=...)` — the manager verifies the platform operator itself and refuses any other user — and management commands use the command-only `operator_access_for_command(command=..., reason=...)`, which records the command, for audited elevated access. When a command or admin path truly needs an unfiltered queryset, it may read from model `all_objects` explicitly under that contract. Self-service account removal does not receive or yield that context: the account row is retained, disabled, and anonymized in place; the orgs-owned `account_deletion_user_reference_organization_ids()` seam validates nullable user relations and returns only the organization IDs whose billing provider state the removal must reconcile, using one indexed query per matching tenant model, and the removal then locks those organizations and reconciles them under each one's ordinary write scope, nulling no reference. The control-plane invitation scrub runs only for an account address allauth verifies, matching it on the global invitation table without elevated scope; an unverified address selects nothing.
- Account removal model: self-service account removal disables and anonymizes the user row instead of deleting it. The row keeps its primary key, so authored records stay attributed to the disabled account (Django admin shows "Deleted user #<id>"); the person's memberships are removed and their invitations scrubbed; the same address can register again, and the old credentials cannot sign in. No cross-tenant write scope is exposed and no reference is nulled. Operator hard delete (Django admin) still deletes the row, and rule 27's `SET_NULL` provenance contract applies to that path.
- Org ownership: System org owns all published-public content (blog feed, public listings, social links). Anonymous visitors see System-org rows; solo authenticated = personal org; saas authenticated = active org.
- Teardown policy: `on_delete=PROTECT` on all tenant-owned FKs + explicit `quickscale_orgs_purge_organization` management command for ordered, FK-safe delete — GDPR-capable, no accidental cascade.
- **Composite-FK deferability policy:** every Option C composite FK (the child-table `organization_id` + local-key pair added by the `_ADD_COMPOSITE_FK_SQL` helper in `orgs/_tenancy_equality.py`) is `NOT DEFERRABLE`. On PostgreSQL 18, `SET CONSTRAINTS <name> IMMEDIATE` on a `NOT DEFERRABLE` FK is a no-op, so the constraint is already effectively immediate — `NOT DEFERRABLE` is the fail-fast choice consistent with the [fail-hard principle](#fail-hard-principle) and requires no `SET CONSTRAINTS ALL DEFERRED` carve-out for fixture/loaddata restores. A conformance test validates that every Option C composite FK is `NOT DEFERRABLE`.
- **`tenant_excluded` marker precedence:** in `is_tenant_model()` (`orgs/tenancy.py`), an explicit `tenant_excluded = "reason"` marker on a model takes precedence over class-hierarchy detection (``TenantModel`` inheritance) — a model marked excluded is never classified as tenant-scoped even if it also inherits tenant machinery.
- **Intentional CASCADE exception:** `OrganizationInvitation.invited_by` remains `on_delete=CASCADE` because a pending invitation is an action attributed to its sender—if the sender's account is deleted, the invitation has no meaningful sender identity and dissolving it along with the sender is the correct behavior. This is a narrow, documented exception to the general SET_NULL rule for user-FKs in tenant-scoped models (`PROTECT` is not allowed; Module Conventions rule 27). The other two `CASCADE` user-FKs are `OrganizationMembership.user` and blog's `AuthorProfile.user` (rows that mean nothing without their user); every other user-FK in `quickscale_modules_*` is SET_NULL (enforced by a conformance test in the orgs cross-module test harness).
- **Last-owner `pre_delete` backstop refusal mechanism:** the orgs `pre_delete` receiver on the `User` model raises (does not silently return/no-op) when the deletion would orphan a shared organization's last owner, matching the [fail-hard principle](#fail-hard-principle) — a caller (admin bulk-delete, management command, a future GDPR erasure path) must see a loud failure rather than believe a refused delete succeeded.
### Clean-Break Migration History {#migration-squash-decision}

**Rule:** QuickScale is pre-1.0 and, for a release before the freeze release, does
not support in-place database upgrades between releases: its supported upgrade
path is a fresh database, no incremental migration history is kept, and each
model-bearing shipped module carries one final-schema `0001_initial`.
Service-style modules carry no migrations. From the freeze release on, a database
created at or after it moves forward in place: an applied migration file is
immutable, and the migrations a later pull adds are applied by `migrate`. The
clean-break posture holds on both sides — there is no cross-release backfill or
compatibility migration class — and the rules below are standing constraints for
anyone adding or changing migrations.

**Freeze release: 0.89.0.** Module migration history is frozen from `0.89.0` on.
`scripts/migration_hashes.json` holds the content identity — the SHA-256 hash of
every numbered migration file — of each shipped module's applied migrations, and
`MIGRATION_FREEZE_VINTAGE` in `quickscale_core.migration_hashes` names `0.89.0` as
the release that carries it. A recorded file is never rewritten in place or
removed, and a schema change ships as a new, higher-numbered migration. The
identity binds every release whose applied vintage is at or after this one:
`quickscale update` refuses to replace an applied migration file and restores the
pre-update content, and `make check-migration-freeze` holds the recorded identity
append-only against the latest release tag. A project on an earlier release keeps
the fresh-database upgrade path and may still have a migration rewritten in
place.

**Standing rules:**

1. **One `0001_initial` per model-bearing module.** The current ten are auth,
   backups, billing, blog, crm, forms, listings, notifications, orgs, and social.
   Each carries its model state in a single initial migration with
   `Migration.initial = True` — the final schema the module held before the
   freeze release; analytics and storage are service-style and carry no
   migrations. From the freeze release on (the paragraph above) that file is
   immutable and a schema change ships as a new, higher-numbered migration.
   Cross-release backfill `RunPython` steps stay prohibited either way. New tenant
   tables ship with `organization_id NOT NULL` from creation.

2. **Each tenant app installs its own RLS.** Every tenant module's `0001_initial` carries its own `RunPython(apply_force_rls, ...)` and is authoritative for its own exact two-policy FORCE-RLS pair. A project-owned tenant app follows the same rule in its own initial migration. The orgs module installs no module-table policy (it runs before enrolled tables exist). `apply_force_rls`/`revert_force_rls` in `orgs/tenancy.py` are the only supported RLS-management entrypoints.

3. **No raw cross-table `organization_id` DML in migrations.** A bounded tripwire test regex-scans for the `UPDATE … SET organization_id` cross-table shape against an explicit allowlist; it is a smoke check, not a soundness proof. Correctness is proven by the `pg_policies`/catalog/data parity gate against the baseline (22 FORCE-RLS tables / 44 policies). Any new allowlist entry must be scoped to exact file-plus-statement identity.

4. **Preserved schema surfaces — keep matching the baseline:** forms' four presets / 16 fields (auto-created via initial data migration), the eight parent UNIQUE constraints and ten composite FKs, and listings' pinned index names.

5. **Quality maxima stay under the fixed threshold lines.** Remediation may only
   reduce a measured maximum or leave it unchanged. A migration that would push
   a metric into a fail column must be compacted with a parity proof preserving
   its exact historical operation, schema, data, and reverse contracts — never
   allowlisted, threshold-exempted, or gate-exempted. See
   §[Quality Thresholds Gate](release_gates_policy.md#quality-thresholds-gate) for the fixed fail/warn
   lines.

**Related docs:** [roadmap.md](./roadmap.md) | [CHANGELOG.md](../../CHANGELOG.md)

**Rejected alternatives (do not re-introduce):**
- ❌ **Per-client Railway deployment** — linear operational overhead per tenant; not a SaaS platform
- ❌ **App-layer-only filtering without RLS** — no defence-in-depth; a single missed filter leaks cross-tenant data
- ❌ **PostgreSQL schema-per-tenant isolation** — schema metadata bloat, migration complexity with many tenants
- ❌ **Supabase as the database provider** — valid for teams that want managed infrastructure, but introduces vendor lock-in and changes the cost/operational model; our self-hosted Railway approach uses the same GUC-carried tenant-context pattern without changing the current contract

**Supabase architecture parity note:** QuickScale's shared-schema + FORCE RLS
model is structurally equivalent to Supabase's — both carry per-transaction tenant
context in a PostgreSQL GUC and isolate with `FORCE ROW LEVEL SECURITY`; only the
injection mechanism differs (PostgREST sets the GUC from JWT claims, QuickScale's
execute-wrapper derives it from the ContextVar at transaction start). The rule this
supports: runtime admin/debug access stays on the restricted role. **BYPASSRLS is
reserved for the migration exception and any future explicitly documented
non-runtime privileged path** — never for a debug or impersonation feature.

**Operator debug mode (VIEW-AS) contract:**
- ✅ VIEW-AS is superuser-only, session-keyed
  (`quickscale_orgs:debug_as_org_id`), and resolved by
  `TenantMiddleware._resolve_debug_org()` ahead of Solo/SaaS resolution
- ✅ Every activation is audit-logged, and a debug banner renders while active
- ❌ No BYPASSRLS — the debug session runs under the same restricted runtime role
  as every other tenant path, so RLS stays fully enforced

Implementation detail: [organizations.md §Operator Debug Mode](./organizations.md#operator-debug-mode-view-as).

**Related docs:** [organizations.md](./organizations.md) (design) | [roadmap.md](./roadmap.md) (current open work) | [arch-audit.md](../others/arch-audit.md) (current risk posture)

---

### Billing Contract

- Authoritative billing configuration lives in `quickscale.yml`, generated Django settings, and environment variables. Planner/apply may write env-var references into managed settings, but Stripe publishable keys, secret keys, and webhook secrets stay environment-only and never persist in QuickScale database rows.
- Billing requires auth-backed users at apply/runtime; QuickScale does not support a standalone billing install without the auth module.
- Billing ships module-owned Django routes for public pricing (`/billing/pricing/`) and the signed-in dashboard (`/billing/dashboard/`). Fresh starter output may link into those pages, but QuickScale does not generate a starter-owned billing React page and does not rewrite existing project React files to adopt billing automatically.
- `WebhookEvent` is the transport-level replay/idempotency gate for incoming billing webhooks.
- `debit_user` is the approved service API for credit consumption.

**Not part of the current contract:**
- ❌ Independent namespace-package distribution for published modules/themes
- ❌ Hook/event systems beyond the documented extension contract
- ❌ Advanced configuration layers beyond the shipped `quickscale.yml` + `.quickscale/state.yml` workflow

---

### Generated-File Ownership (Beta-Migration Taxonomy) {#generated-file-ownership-taxonomy}

Rules and inventory: [generated_file_ownership.md](generated_file_ownership.md#rules).

---

### Beta-Site External Verification Scope {#beta-site-external-verification-scope}

**Decision:** Verifying the *deployed* state of `bap-web` — confirming a specific commit's generator/template changes
actually reached that running site, checking their live Redis
configuration, or inspecting/patching their donor-owned `settings/production.py`
— is **permanently out of scope for this monorepo's automated tooling and for
any coding-agent session operating inside it.** Neither the site's repository nor
its Railway deployment is reachable from here; this is a structural property
of the two-repo maintainer workflow (`quickscale_devtools/beta_migration/`,
[beta-site-migration.md](../planning/beta-site-migration.md)), not a
credentials gap expected to close.

**Why:** the beta sites are external maintainer-operated repositories; no tooling in this repo can reach their Railway shells or push to them.

**What stays in scope (and is not affected by this decision):** everything
this repo *can* verify mechanically — the generator templates themselves,
the beta-migration file taxonomy and its conformance gate,
and the launcher env-pair contract's correctness in the templates it emits.
Those are the actual defect classes; this decision
only scopes out the one step no in-repo mechanism can perform: confirming a
human maintainer applied the fix to a live external deployment.

**Standing rule for future findings:** any roadmap item, tech-audit finding,
or arch-audit red flag whose acceptance criteria requires inspecting or
patching the live `bap-web` deployment (not just this
repo's generator output) is closed on discovery with a pointer to this
section, rather than left open as a blocked roadmap item. Record the
manual-verification ask as a maintainer to-do in
[beta-site-migration.md](../planning/beta-site-migration.md) instead of a
roadmap.md checklist entry — the roadmap tracks repo-local implementation
work, not manual maintainer operations against external infrastructure.

**Related docs:** [roadmap.md](./roadmap.md) | [arch-audit.md live findings](../others/arch-audit.md) | [beta-site-migration.md](../planning/beta-site-migration.md)

---

### Test-Commons Ownership Rule {#test-commons-ownership}

**Rule:** Define the boundary between
org-context runtime helpers and cross-module test plumbing, citing the
`apply_force_rls`/`revert_force_rls` seam as the existing house pattern
for a working shared-commons precedent.

**Ownership:**

1. **`quickscale_modules/orgs/` owns org-context runtime helpers** — the
   `reset_current_org_id()`, `org_scope()`, `operator_access()`, and
   `operator_access_for_command()` public
   API surface is owned by the orgs module and lives in
   `quickscale_modules_orgs.current_org`.  No test code may maintain a
   private copy of these helpers.
2. **`tests_shared/` owns cross-module test plumbing** — reusable fixture
   modules (e.g. `isolation.py`, `reset_state.py`) and any future
   cross-module test infrastructure live under `tests_shared/`.  No module
   conftest may maintain a private copy of the per-test state-reset
   contract or any sanctioned cross-module test utility that already exists
   in `tests_shared/`.  The one core-shipped exception is the shared
   test-settings base and conftest plugin (rule 18): they live in
   `quickscale_core.testing`, because every module suite already depends on
   core and a split module branch carries core while it cannot import the
   repo-root `tests_shared/` package.

**Precedent — `apply_force_rls`/`revert_force_rls`:** The
`apply_force_rls`/`revert_force_rls` seam is the house pattern for a working
shared-commons relationship.  Orgs owns the RLS policy-management helper,
each tenant module calls it during its own migration, and no module
maintains a private copy.  This same principle extends to the test
plumbing layer.

**Enforcement:** Any module conftest that defines a fixture whose
documentation or identifier references resetting `app.current_org_id`,
`SET ROLE`, execute-wrapper priming memo, or the Django cache MUST import
the shared `reset_test_state` fixture from `tests_shared.reset_state`.
New cross-module test utilities must be placed in `tests_shared/` rather
than duplicated across module conftests.

**Related docs:** [roadmap.md](./roadmap.md) | [CHANGELOG.md](../../CHANGELOG.md)

---

### Rendered-Link Sanitization Ownership {#rendered-link-sanitization-ownership-sa98}

**Decision:** The orgs module owns the narrow shared rendered-link sanitization
seam used by the blog and listings modules. The public API is
`quickscale_modules_orgs.sanitization.sanitize_href` and
`quickscale_modules_orgs.sanitization.sanitize_rendered_html`; the consumer
views import the rendered-HTML helper directly and do not define or re-export
local aliases. Direct primitive tests live with the orgs owner, while blog and
listings retain their detail-view regression coverage.

This is a narrow existing-dependency/distribution exception: blog and listings
already depend on and distribute alongside orgs, so placing this security
primitive there avoids a second implementation without adding a new runtime
dependency or package. It is not a generic commons decision, and orgs must not
become a general-purpose utility bucket. New shared helpers still require a
separate ownership decision based on an existing dependency and a concrete
module boundary.

The sanitizer contract remains deliberately limited to scheme checks for
double-quoted rendered `href` attributes and the established allowed-link
semantics; this decision does not authorize unrelated HTML or URL utility
surface.

### Frontend Theme Source De-Specialization {#frontend-theme-despecialization-dormant-files}

**Rule:** `frontend/src` must be project-agnostic and byte-identical across all projects on
the same theme version. Project- and module-specific facts flow only through the existing
`window.__QUICKSCALE__` runtime seam — never baked into frontend source at generation time.
No second injection mechanism.

**Module availability:** the generator emits **every** module's frontend files unconditionally;
absence of a module is expressed only as a runtime flag (`false`), gating routes/rendering.
Dormant module files in generated trees are accepted (tree-shaken from the built bundle). Do
not narrow the emitted file set or the `QuickScaleModules` TS interface per project.

**Project identity** (name, etc.) is read from runtime config, not JSX/source literals. Jinja
specialization is confined to Django-side templates and at most `package.json`.

Rejected: per-project source specialization plus an ownership-manifest overlay — it preserves
the per-file migration merge and a second hand-synced list.

Module Conventions rule 31 fixes what the seam's `modules` flags mean (installed and enabled) and
has the `quickscale_seam` runtime template tag render them from the discovered module set at
request time.

---

<a id="af7-installed-wheel-module-discovery"></a>
## Prohibitions (Critical - DO NOT)

Prohibitions stated in their owning section (database, packaging, tools, fail-hard, wiring,
lockstep, tenant isolation) are not repeated here. The rest:

- ❌ Running `quickscale plan`/`quickscale apply` inside the QuickScale repository
- ❌ Route-slug-based org resolution for content routes (`/orgs/<slug>/crm/...`); content uses
  flat routes plus the session active org; the org-admin API keeps `/orgs/api/<slug>/`
- ❌ Connecting generated apps in saas/prod mode under a BYPASSRLS or SUPERUSER role
- ❌ Runtime dynamic `INSTALLED_APPS` modifications
- ❌ DI frameworks or service registries; `AppConfig`-declared capabilities and the listed core
  ports are the allowed forms ([module_conventions.md](module_conventions.md#module-conventions))
- ❌ Custom abstract provider interfaces or app-defined multi-provider contracts
- ❌ Custom database table naming (Django's `app_label` default only)
- ❌ Ad hoc or undocumented module HTTP APIs beyond the documented module routes and webhooks
- ❌ Unpinned versions in production
- ❌ Executable code or deep nesting in config files (pure, flat YAML only)

## Package Structure

Individual `quickscale_modules/*` packages are never installed or resolved outside the monorepo;
they run wired together by `quickscale plan`/`quickscale apply`.

- ✅ The root `pyproject.toml` is the single dependency-resolution source: every module is a
  `path = "...", develop = true` dependency resolved into one `poetry.lock`
- ✅ `quickscale_modules/` is a PEP 420 namespace (no `__init__.py` at the namespace root;
  CI fails the build if one exists); `quickscale_core` is a regular package
- ✅ `src/` layout, tests in a parallel `tests/` directory; no nested package names
- ❌ Per-module `poetry.lock` files, sibling-module version-range dependencies, or any other
  standalone-install machinery for a module package
- ❌ Treating a package `README.md` as authoritative over root docs or decisions.md

Layout and naming/import matrix: [repository_layout.md](./repository_layout.md).
Module responsibility boundaries:
[implementation_contract.md §Module Boundaries](./implementation_contract.md#module-boundaries).
