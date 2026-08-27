# v88 Ticket Context — Concepts and Implementation Notes

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **v88 Ticket Context**
> **Related docs**: [Roadmap](roadmap.md) (authority for ticket metadata) | [Decisions](decisions.md) | [Validation Policy](validation_policy.md) | [Arch audit](../others/arch-audit.md) | [Tech audit](../others/tech-audit.md)

## What this document is

The [roadmap](roadmap.md) says what each v88 ticket must achieve.
This companion says *why the problem exists*, *what mental model to hold*, and *where the
code actually lives*. It is explanatory, not authoritative: if this document and the
roadmap disagree, the roadmap wins.

Read the roadmap ticket first, then the section here.

**This page deliberately carries no second set of schedulable classification rows.** Formal
band, tier, worktree, merge-position, dependency, slot-ownership, and validation-station
metadata live in the roadmap and only there. The conceptual notes here may explain why an
ordering or resource relationship exists, but only the roadmap states its current scheduling
value or status. The `scripts`-side enforcement checks section *coverage* (one context section
per open roadmap ticket, with no orphans), rejects copied classification rows, and rejects
prose claiming a roadmap-open dependency is closed.

It covers every open v88 ticket entry plus the post-v88 entries. Closed tickets are not
covered as open sections; their closure evidence lives in [CHANGELOG.md](../../CHANGELOG.md).
The completed SA167a and SA167d handoffs appear only as historical context in the shared
conceptual section below, without creating closed-ticket sections.

---

## The mind map

The open release work is one principle with four failure modes. Every ticket is a leaf.

```text
                  ONE FACT, ONE HOME
                  ─ and when the home cannot be read, STOP ─
                                  │
            ┌─────────────┬───────┴───────┬──────────────┐
            │             │               │              │
        DUPLICATED      SILENT         UNOWNED       UNENFORCED
         AUTHORITY     FALLBACK       LIFECYCLE       POLICY
            │             │               │              │
          SA118         SA165           SA135          SA166
          SA163         SA152           SA161            │
          SA160           │               │         (testimony
          SA164       (state/tool      (DB, dead       trail)
            │          fallbacks)       code)
       (defaults, CI env,
        cookies, watchlists)
```

**The one sentence:** *Every fact should have exactly one home, and every consumer should
read it from that home. When a consumer cannot read it, the system should stop, not guess —
and the gate that proves all of this must itself actually run.*

That last clause is what the revised priority model added. Auditing the gate layer found
an enforcement failure underneath the four open failure modes; the gate-layer prerequisite
and SA162 correction are now complete, with their evidence archived in the changelog.

| Failure mode | What it looks like | Tickets |
|---|---|---|
| **Duplicated authority** — the same fact is written down in two or more places, so they drift | manifest defaults restated in imperative code; the PGDG install copied across 14 stations | SA118, SA163, SA160, SA164 |
| **Silent fallback** — a component cannot find the authoritative answer, so it substitutes a plausible one and continues | The closed SA150 stopped the explicit-wheelhouse → manifest fallback; a corrupt state file still returns silently; a skip where a failure belongs | SA165 |
| **Unowned lifecycle** — a resource is created but nobody is responsible for its identity or destruction | the integration gate assumes a PostgreSQL server someone else started; dead code nobody deletes | SA135, SA161 |
| **Unenforced policy** — a rule exists only in a human's head | no requirement that a behavioural commit leave a trail | SA166 |

The `scripts/test_*.py` conformance population now has an owning registered execution
context. Its closure evidence is archived in [CHANGELOG.md](../../CHANGELOG.md), so the
scope allowlist, gate registry, parity, and quality-baseline suites run through the same
declared gate layer they protect.

The gate-layer closure evidence, including the current scripts census, registry projection,
hosted job closure, and isolation Make entrypoint, is archived in [CHANGELOG.md](../../CHANGELOG.md).

---

## SA118 — Project every declared manifest default into wiring

### The mental model

Each module carries a `module.yml` manifest that **declares** its configuration surface. From `quickscale_modules/storage/module.yml`:

```yaml
config:
  mutable:
    backend:
      type: string
      default: "local"
      django_setting: QUICKSCALE_STORAGE_BACKEND
      validation:
        choices: ["local", "s3", "r2"]
    media_url:
      type: string
      default: "/media/"
      django_setting: MEDIA_URL
  immutable:
    private_media_enabled:
      type: boolean
      default: false
```

Every entry states four things: a type, a default, the Django setting it maps to, and (sometimes) validation. `mutable` options must have a `django_setting` — `quickscale_core/src/quickscale_core/manifest/loader.py:242` enforces it. `ModuleManifest.get_django_settings_mapping()` (`manifest/schema.py:225`) already exposes the name→setting map.

So the declaration is rich and validated. The question SA118 asks is: **does the generated project's wiring actually reflect every declared default, or do some defaults exist only inside imperative Python that re-states them?**

A concrete example of the second pattern lives in the closed SA150's file:

```python
backend = str((module_options or {}).get("backend", "local")).strip().lower()
```

That `"local"` is `storage.backend`'s manifest default, retyped in `module_dependency_sync.py`. Change the manifest and this code keeps the old default. It is the same class of bug as the completed pin-authority work, one layer up.

### The scope boundary — this is the important part

There is a much larger, tempting project here: converting all imperative module wiring to a declarative manifest-driven pipeline. **SA118 explicitly is not that project.** The acceptance says: *"the imperative-to-declarative migration is not attempted — out-of-scope seams are ticketed, not converted."*

The line to hold:

- **In scope:** a default is *declared* in a manifest, and generated wiring does not carry it (or carries a stale copy). Fix the projection.
- **Out of scope:** a behaviour is imperative and has no manifest declaration at all. Do not invent a declaration for it. File a ticket.

The distinction is "is there already a declared fact being ignored?" — not "could this be declarative in principle?"

### Emission parity — expect this to be the bulk of the work

Changing what the generator emits collides with `quickscale_core/tests/fixtures/sa90_emission_manifests.json`. Read its `_provenance` block: it holds *exact path/hash/mode manifests* for three generator variants, deliberately built independently of the production emission mapping so it is a real check and not a mirror.

Its `baseline_evidence` entries show the established convention — each past rebaseline records ticket id, date, what changed, and which specific hashes moved:

> `"sa106": "Regenerated 2026-07-20 — three identity-bearing frontend source templates converted from .j2 to static verbatim-copy files (SA106). ... Deltas: useModules.ts.j2→static, ... 3 fixture hashes updated: useModules.ts, Dashboard.tsx, Sidebar.tsx."`

*"rebaseline emission parity with per-file rationale"* means adding an entry in exactly that register. A bulk regeneration with the note "updated hashes" destroys the fixture's value — the whole point is that a human certified each delta was intended.

---

# Service-backed lifecycle

The remaining lifecycle ticket asks: *who owns the lifecycle of a thing we create?*

## SA135 — Give test suites an owned PostgreSQL lifecycle

### The mental model

Compare the two database-backed gates as they exist today:

**The E2E gate owns its database.** `scripts/test_e2e.sh:535`: *"pytest-docker will automatically start PostgreSQL"*, backed by `quickscale_core/tests/docker-compose.test.yml`:

```yaml
services:
  postgres:
    image: postgres:18-alpine
    ports:
      - "5432"   # Dynamic port — Docker assigns an available host port
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user -d test_db"]
```

Started on demand, health-checked, dynamically ported, torn down after.

**The integration gate borrows one.** `scripts/test_integration.sh`, header:

```
# Requires PostgreSQL 18 running on localhost:5432.
#
# Prerequisites:
#   - PostgreSQL 18 running on localhost:5432
#   - All test databases pre-created (see ci.yml create-test-databases step)
#   - A LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER role ... with
#     ownership + schema grants on all module test databases
```

Three preconditions that **somebody else** must have satisfied, out of band. On hosted CI a workflow step does it. On a developer machine, a human did it once, months ago, and may not remember how.

SA135 is: make the integration gate own its server the way the E2E gate already does. The pattern is proven and in-tree — this is largely propagation, not invention.

### Why the fix is delicate

The role contract is not incidental. `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` — specifically `NOBYPASSRLS` — is what makes row-level-security tests **meaningful**. A superuser bypasses RLS entirely, so isolation tests running as one would pass without proving anything. `scripts/provision_test_roles.sh` and `scripts/test_isolation_conformance.sh` exist to enforce this.

A hasty containerised swap that connects as the default `postgres` superuser would leave every integration test green and every multi-tenant isolation guarantee unverified. That is the worst possible outcome for this repository, given the locked child-table RLS policy. **Preserving the role contract is the acceptance criterion that matters most.**

### The negative control

*"the asserted-unavailability negative control still fails loudly when the server cannot be provisioned, rather than skipping"*.

The tempting shape for provisioning code is:

```python
if not postgres_available():
    pytest.skip("PostgreSQL not available")
```

That converts an infrastructure failure into a green build with silently zero integration coverage — the same silent-fallback family the closed SA150 addressed, one layer up. If provisioning fails, the gate must fail. There is an existing asserted-unavailability control; it must survive the rewrite.

### Proof

*"`make test-integration` passes on a machine with no PostgreSQL running"*. Test it honestly — stop any host PostgreSQL, confirm nothing is listening on 5432, run the gate. If it passes because it quietly found a server you forgot about, you have proven nothing.

### Documentation

`docs/technical/validation_policy.md` currently encodes the out-of-band assumption:

> Integration | `make test-integration` | ... | PostgreSQL 18 per-module test DB | `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER`

and the Testing Standards section describes the precondition in prose. Both need updating — this ticket changes a documented contract, which is why `validation_policy.md` is on its conflict surface.

---

## SA163 — Derive the CI PostgreSQL environment from one authoritative source

### The mental model

The gate registry answers *which* gates run in *which* contexts. It does **not** answer
*what environment those gates require*. That second question is answered nowhere
declaratively — it is hand-replicated as shell.

### The census

Thirteen stations state the same environment:

| Thing | Copies | Where |
|---|---|---|
| PGDG PG18 install | 4 | `ci.yml:92-107`, `ci.yml:408-427`, `publish.yml:161-187`, `e2e.yml:74-91` |
| PG18 verification | 4, **divergent** | three check `command -v` *and* `--version \| grep "(PostgreSQL) 18"`; `e2e.yml:92` checks only `test -x` |
| `createdb` lists | 4 | across the same workflows |
| grant loops | 4 | ditto |
| `QS_*_DB_USER` blocks | 5 | ditto |
| the whole thing **as a Python literal** | 1 | `scripts/test_gate_parity.py:1125-1180` transcribes the shell verbatim |

That fourteenth station is the tell: a parity test that *transcribes* what it checks is not
an independent oracle — it is a fifteenth copy wearing a test's clothes.

### The live question this ticket must settle

`nightly-bypassrls.yml:81-82` installs plain `postgresql-client` — Ubuntu 16.x, **no
PGDG** — while creating `test_quickscale_backups` and setting `QS_BACKUPS_DB_USER`. That
runs against `ci.yml:93-95`'s own statement that the backups DR engine enforces a
PostgreSQL 18 `pg_dump`/`pg_restore` contract which 16.x fails.

Determine whether `make test-bypassrls` actually reaches a `pg_dump`/`pg_restore` path. If
it does, this is a **live defect**, not a cosmetic divergence, and it gets fixed here.

### Two divergences that are correct — do not "fix" them

Both were verified this audit pass. Refactoring blindly will break them:

1. The 6-entry `QS_*_DB_USER` block at `ci.yml:627-632` is **exactly** `orgs` plus
   `RLS_MODULES` from `test_isolation_conformance.sh:141`. It is derived, not truncated.
2. The isolation job's 11-database list **omits `backups`** because that job runs no
   backups tests.

Document both as deliberate in the refactor, or the next reader will "unify" them away.

### The option choice, already made

**Selected shape**: one `scripts/provision_ci_postgres.sh`, four callers, and a module list
derived from the discovery shim exactly as `check_sa117_scope.py:48` already does. The SA135
surface includes `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, the
`Makefile`, and the documented database precondition; SA163 addresses the same provisioning
contract.

### Non-negotiable invariants across the refactor

`QUICKSCALE_ALLOW_BYPASSRLS: "0"` at `ci.yml:626` and the restricted-role isolation
connection must survive **unchanged**. These are the same RLS-meaningfulness guarantees
SA135's role contract protects; losing them here loses them everywhere.

---

# Bounded independent fixes

Each has a small, well-understood blast radius and remains bounded to its stated concern.

## SA160 — Share one correct CSRF-token helper in the React theme

### The mental model

Django's CSRF protection needs the SPA to read the `csrftoken` cookie and echo it in an
`X-CSRFToken` header. `document.cookie` is a single flat string, and **cookie names are not
unique in it** — the same name can appear more than once at different domain scopes.

Any parser that assumes uniqueness is a latent bug waiting on a deployment topology.

### The concrete defect

Eleven identical lines appear twice — `themes/showcase_react/src/hooks/useApi.ts:20-28` and
`src/components/forms/FormRenderer.tsx:206-211`. Both split `document.cookie` on
`"; csrftoken="` and accept the result **only when it yields exactly two parts**.

Two `csrftoken` cookies yield three parts. So:

```
getCsrfToken() → ''
   → buildRequestHeaders (:89-94) skips X-CSRFToken
      → Django rejects every POST/PUT/PATCH/DELETE with 403
```

GETs keep working. **The app looks alive and merely refuses to save**, and no error names
the cause.

### Why the trigger is ordinary, not exotic

An `app.example.com` deployment alongside a `.example.com` cookie. That is the outcome of
setting or changing `CSRF_COOKIE_DOMAIN`, of a sibling Django app on another subdomain, or
of a stale apex-scoped cookie in one user's browser. This is the internet-facing generated
project — deployment reality #3.

It **fails closed**: availability, not a security hole. That is why it is Tier 2 and not
higher. But there is no shared helper, no fetch interceptor, and no template-injected
token, so **no layer-up guard exists** — every call site is on its own.

### Implementation shape

One helper in `src/lib/`, following Django's own documented `getCookie`: split on `'; '`,
**match the name exactly**, `decodeURIComponent` the value. Iterate; never count segments.
Both call sites import it, and **no third variant remains** — the duplication is half the
finding.

A `vitest` table test over `'csrftoken=A; csrftoken=B'`, `'sessionid=x; csrftoken=A'`,
`'csrftoken=A'`, `''` — first three non-empty. The first case is the one that is red today.

Note the tech audit records "no `src/lib/http` seam" as a structural smell; this ticket
creates that seam. Place the helper accordingly.

---

## SA161 — Remove the dead `get_client_ip` definitions from generated settings

### The mental model — the Django fact that makes this dead code

`django.conf.settings` copies **only uppercase names** off the settings module. A
lowercase function defined in `settings/base.py` is not reachable as
`django.conf.settings.get_client_ip`. It never was.

### The concrete defect

`templates/project_name/settings/base.py.j2:61` and `settings/production.py.j2:123` both
define a module-level `get_client_ip(request)`. The production copy **rebinds** it under a
comment claiming the rebind exists *"so that production defaults … are actually in effect
at request time"*.

That comment is the actual defect. The code is merely dead; the comment asserts a mechanism
that does not exist, and a future reader will trust it. Grep across all templates returns
only the two definitions — nothing calls either.

The live implementation is `quickscale_modules_orgs.current_org.get_client_ip`, which reads
the **uppercase** `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT` settings dynamically and is
correct.

### Implementation shape

Delete both, or leave each as a comment pointing at the orgs helper. **Either way remove the
misleading behavioural comment at `production.py.j2:119-122`** — that is the part that must
not survive.

Keep unchanged: the uppercase settings themselves, and the `REST_FRAMEWORK["NUM_PROXIES"]`
recomputation. Both are live.

Assert with a test that proxy-aware client-IP resolution is unchanged — this touches
security-relevant settings, and "it was dead code" is a claim that deserves proof.

### Emission parity

This edits generated-project templates, so the SA90 emission-parity fixture needs a
rebaseline with per-file rationale — the same treatment described under SA118.

---

## SA165 — Discharge the tech-audit watch items that carry an action

### The mental model

The tech audit's *Notes* hold thirteen items. Most are **accepted trade-offs** or are owned
elsewhere — the closed SA150 discharged the local-wheelhouse seam, while integration-branch CI,
generator lock generation, the DB-free healthcheck, the
CRM count fallbacks, and non-durable atomic state writes are each recorded as **deliberate
and explicitly out of this ticket's scope**.

Do not re-litigate those. Four items carry a concrete action; this ticket is exactly those
four.

### 1. `flush_empty_consolidated_sections` swallows a corrupt state file

`quickscale_core/src/quickscale_core/schema/state_schema.py:386-388` returns silently on
`yaml.YAMLError, OSError`, skipping the explicit `modules: {}` / `managed_files: []`
markers that downstream readers use to distinguish *"M2 has spoken"* from *pre-M2 state*.

The trigger is narrow — the file was just written successfully by `save()` — but this is
precisely the shape the Fail-Hard Principle names (`decisions.md:634`, `:716-732`), and
`tech-audit.md` is the declared SSOT for that class. Same family as the closed SA150, one layer over.

**Raise or report. A regression test must assert the raise, not a log line.**

### 2. The isolation-gate skip allowlist matches on message, not identity

`scripts/test_isolation_conformance.sh:184` keys on
`message.startswith('got empty parameter set')`. That silences an empty parameter set on
**any** of the eleven parametrized tests in `test_tenant_table_conformance.py` — not only
the two `PENDING_REMEDIATION` ones its own comment describes.

A message prefix is not an identity. Narrowing it to the two test names costs one line.
Prove it: deliberately empty the ENROLLED set and confirm the gate turns **red**.

### 3. `_HOST_DEPENDENT_PATHS` is a new hand-maintained exception station

`be5cf024` added `frozenset({".env"})` to the SA90 emission byte-parity gate
(`quickscale_core/tests/test_generator/test_generator.py:1023`). The justification is sound
and the `755`/`644` mode normalization correctly removes a umask dependency.

But this is an **exception list on the repository's strictest gate**. The monotonicity rule
to write down: a second entry deserves scrutiny, a third deserves a derivation. Add the
per-entry rationale and that escalation note — or derive it now.

### 4. Generated local-development credentials are predictable by construction

`generator.py:507-508` derives `runtime_db_role = f"{package_name}_app"` and
`runtime_db_password = f"{role}_password"` into `db/init.sql`, `docker-compose.yml`, and
`.env.example` — none of which `.gitignore.j2` excludes.

**Safe as shipped**: no published DB port, local dev only, production supplies
`RUNTIME_DATABASE_URL` from the environment. The gap is that it is undocumented. State
explicitly in `OPERATIONS.md` that these credentials must not survive into any shared
environment. Documentation only — do not change the derivation.

---

## SA164 — Adjudicate the arch-audit watchlist's unevaluable and drifted items

### The mental model

A watch item is a bet: *"this is not a problem yet, and here is the trigger that would make
it one."* A watch item whose trigger **cannot be evaluated** has stopped being a bet and
become debt — it costs a read every audit pass and can never fire.

Five items are carried. Three are simply not fired and need no work. Two carry explicit
actions, and one is a naming question that becomes load-bearing on a specific trigger.

### 1. The SA92 migration-squash tuple — artifact found, re-anchor remains open work

The artifact is
`quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`, a bounded
literal tripwire for cross-table `UPDATE … SET organization_id` migration DML; it is
not a schema-parity proof. Its `_migdir()` helper reads the inert `django_apps:`
manifest key and silently guesses a conventional path when absent, while its parity
backstop still names the retired `v87` baseline. The current regenerated migrations and
discharged S4 BYPASSRLS prerequisite are settled; SA164 owns the `_migdir()` helper
correction and parity-backstop re-anchoring.

### 2. Privileged-command pair — values agree, claimed authority does not

`production.py.j2:185` and
`quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py:36` both hold
`frozenset({"migrate", "createcachetable"})`. The values are **verified equal**.

But the `apps.py` docstring calls itself *"the single source of truth for which commands are
privileged"* while the template holds an independent copy. The defect is the **claim**, not
the value.

Make the claim true — either the template reads the runtime frozenset, or the docstring
stops claiming sole authority — **with a test asserting the two cannot diverge.** A
governance artifact that says "single source of truth" beside a second copy is worse than
silence, because it stops the next reader from checking.

### 3. `trigger_inputs` has drifted from its name

`check_gate_parity.py:2652-2690` uses the field as a **bidirectional partition of
`e2e.yml`'s path allowlist**, not as *"what changes should trigger this gate"*. That is why
`check-core-compat`'s trigger reads `quickscale_modules/backups/**`.

**Not a defect** — the check it performs is real and exact. It is a name that lies about a
correct mechanism. It becomes load-bearing the moment a gate is ever *skipped* on the basis
of `trigger_inputs`, because then the name's meaning and the field's meaning diverge in
production.

Rename it, or record the actual semantics plus that promotion trigger in the docstring and
schema description.

### And restate the three that are not fired

Module universe in environment lists, frontend runtime module keys, and the now-absorbed
watch half of Finding 13. Keep their triggers intact — restating is the work, not removing.

---

## SA166 — Require a testimony trail for behavioural commits

### The mental model

Every other ticket in this release makes a *machine* tell the truth. This one makes a
*commit* tell the truth.

### The evidence

`d3d4c633` and `d4b0e834` were both titled **"v0.87.0: QuickScale 0.87.0"** while in fact
changing hosted and publish provisioning. `d3d4c633` also left a repository conformance test
red — a stale publish-parity oracle, since repaired and closed.

Both audits independently flagged the same shape: **a release-shaped message carrying a CI
topology change**. It was read closely only because the arch audit's delta-classification
step treats unlabeled-behavioural commits as read-at-full-depth. Absent that convention, it
would have shipped unexamined — and it did ship a red test.

### Why it is Tier 3

The audit records this as **maintainer-process risk**, not a source finding. The registered
gate layer is an executed context, so this ticket can add its process evidence without
reopening the gate-suite work.

### The design constraint that decides whether this succeeds

*"false-positive cost is measured on the existing history and the rule is narrowed until it
is quiet on legitimate release commits."*

A noisy process gate gets a bypass flag, and a bypass flag gets used by default. Measure the
rule against real history **before** turning it on. If it fires on legitimate release
commits, narrow it — do not add an override.

Scope: a change touching `.github/workflows/`, `scripts/gate_registry.json`, or the
provisioning stations requires a roadmap ticket reference or a `CHANGELOG.md` entry,
enforced mechanically. Registered in `scripts/gate_registry.json`, passing
`scripts/check_gate_parity.py`. Prove it with a deliberately introduced untitled workflow
change, reverted before merge.

---

# Post-v88 — recorded backlog

These three are in the roadmap so the findings are not lost. Listing a sub-item here does not
authorize implementing it.

## SA152 — Refresh the beta-migration maintainer targets

The 2026-08-21 audit found the **mechanics current**: the Makefile flag surface (`DONOR`,
`RECIPIENT`, `DRY_RUN`, `CONTINUE`, `REPORT`) matches `build_argument_parser()`, every
command in `VERIFICATION_COMMAND_SPECS` still exists, and the file-ownership taxonomy is in
sync and enforced by 7 passing conformance tests. So this is not a rot ticket. Four residual
gaps:

- **The SA151 collision is now a settled prerequisite.** The workflow's verification stack runs
  `quickscale manage migrate` against a recipient that may carry an existing database. SA151's
  clean-break implementation makes a **fresh database the only upgrade path**, invalidating the
  in-place workflow's implicit assumption; SA152 must reconcile that mismatch in its own scope.
- **No end-to-end exercise.** The targets appear in no CI workflow and no
  `scripts/gate_registry.json` entry. Coverage is unit-level taxonomy conformance only, so
  breakage surfaces for a maintainer **mid-migration** — the worst possible moment.
- **Silent skip in the conformance gate.** `_template_emitted_paths()` calls
  `pytest.skip()` when the template tree is not found, so a path-resolution regression turns
  the ownership gate **green instead of red**. Same silent-fallback family as the closed SA150 and
  SA165.
- **Stale doc provenance.** `beta-site-migration.md` is headed *"shipped in v0.81.0"*
  against `VERSION` 0.87.0, and describes the tool as *"backed by Python scripts under
  `scripts/`"* when `scripts/beta_migrate.py` is an eight-line wrapper over
  `quickscale_devtools`.

## SA153 — Close the property-portal basics gap in `listings`

**A high-value post-release work item**, driven by the planned `buenosairesproperties.com`
migration. The framing that matters: the gap is **not module existence**. `listings` ships a
deliberately generic `AbstractListing` plus a concrete `Listing`, and `blog` is
substantially complete. The gap is **property-vertical depth and public presentation**, and
every sub-item is a *basic* — a real-estate portal cannot launch without it.

The structural problem underneath most of the sub-items: the documented extension answer is
**subclassing `AbstractListing`**, but `views.py`, `urls.py`, `admin.py`, and `ListingFilter`
are all bound to the **concrete** `Listing`. So subclassing today yields a model and an admin
base but **no working public views, URLs, or filters** — the Tier 2 abstract-model contract
in [module-extension.md](module-extension.md) is half-delivered.

Two project constraints bind every sub-item:

- **Every new child table carries its own `organization_id` column** with its own RLS policy
  — the locked Option C child-table policy in [decisions.md](decisions.md). No parent-join
  RLS, including for `ListingImage`.
- RLS-boundary coverage must match the existing `test_rls_boundary.py` pattern.

Sub-items: image galleries, property attributes, attribute filtering + keyword search
(the module README currently **claims** search that does not exist), multi-currency (a
hardcoded `$` against a single-currency `DecimalField`), i18n (`USE_I18N = True` with no
`LocaleMiddleware`, no locale dirs, no marked strings), themed public presentation,
listing-linked lead capture into `crm`, SEO (no sitemaps, no `robots.txt`, no Open Graph
anywhere in the tree), and a public JSON read API.

## SA154 — Property-portal optional capabilities

An inventory of optional capabilities, not an implementation instruction. Map/geocoding,
saved searches and match alerts,
agent/office profiles, portal syndication feeds, virtual tours, featured placement tied to
the `billing` credits ledger, blog↔listing cross-linking, and PostgreSQL `SearchVector`
full-text search.

Each sub-item needs its own acceptance criteria if it is promoted, or a written rationale if it
is dropped.

---

## Reusable reasoning traps

Worth holding as a set, because each appears in more than one ticket:

- **The tautology trap**. A test that reads the authoritative value and asserts the
  authoritative value passes for any value, including nonsense. Derive *wiring* assertions;
  keep *negative controls* literal.
- **The green-by-absence trap** (SA135, SA152, SA165). Skipping, filtering,
  and unresolvable paths all produce green. Every one of them must be made to produce red.


---

## SA167c — module wiring standardization

This open roadmap entry carries conceptual context for the module-wiring standardization. The
completed SA167a and SA167d handoffs are retained only as historical context; their completion
evidence is archived in [CHANGELOG.md](../../CHANGELOG.md). Ticket metadata lives in the
[roadmap](roadmap.md), not here. SA167b's completed relocation and P4 acceptance are likewise
archived there rather than described as open work here.

**The concept.** A QuickScale module is two things stacked. Underneath is an ordinary
Django app — `apps.py`, models, migrations — with no QuickScale divergence at all.
On top is one QuickScale-specific thing: the *adapter*, which is the machine-readable
form of the install instructions a normal Django library writes in its README.
Django assumes a human reads "add this to `INSTALLED_APPS`" and types it; `quickscale
apply` generates the project, so that instruction has to be data.

**What went wrong.** That one fact — which Django apps a module contributes — had five
competing representations at kickoff: a wiring projection in six manifests, a Python literal
inside core for five more, nothing at all for `social`, an inert `django_apps:` key in eleven
manifests that no code reads, and a per-module function pair in the CLI. SA167a's implementation
and accepted root quality-gate oracle are recorded on the integration branch:
all five former core literals now come from their own manifest projections. SA167b subsequently
moved every module: P1/P2 relocated analytics, backups, blog, forms, listings, and notifications,
and P3 relocated auth, orgs, and storage, leaving no per-module block in core. Its P4 acceptance
then confirmed the twelve module-owned adapters, generic-only core registry, restoration behavior,
and unchanged emission parity; the accepted boundary is merged integration-branch state. When a fact
lives in five places, no one can tell which is the answer, and `social` shipped models
and a migration that no generated project ever installed.

**The rule** is now written in
[decisions.md §Module Wiring Authority](./decisions.md#module-wiring-authority): every
module owns its adapter, and declares its apps once, in its own `module.yml`. These four
tickets make the tree match it — `a` declares, `b` relocates, `c` retires the inert key
and adds the gate that keeps it true, `d` drains the CLI.

**Why the split is by phase and not by module.** All nine core-side blocks began in one
1,508-line file, and every phase has had to edit that same file. The phase boundary keeps one
logical adapter migration understandable without turning it into nine separate conceptual sections.
