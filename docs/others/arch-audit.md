# Structural Autopsy: QuickScale

Audited: `8e4122f2` (`v89`) · 2026-10-05 · working tree clean · prompt: deep-architectural-audit v9

> Live structural findings only. Findings are identified by their **slug**; ordinal numbering is
> pass-local and is not a stable identifier (see
> [decisions.md → Document Responsibilities](../technical/decisions.md)). Closed findings and
> prior-pass narratives live in [CHANGELOG.md](../../CHANGELOG.md) and version control.

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code generator and scaffolding platform**: a Click CLI, a
Django 6 project generator, and twelve first-party modules embedded into generated projects by
`git subtree` and upgraded by `quickscale update`. Generated projects run PostgreSQL 18,
Vite/React, Docker, and Railway. Public contracts: the CLI; `quickscale.yml` and applied state;
module manifests (option schemas, URL mounts, and now UI routes, SA235); the generated trees;
upgrade semantics; and `quickscale_core.runtime.settings`. Two **deployment realities**: the
generator with its CI, and the generated projects (`bap-web`, `experto-ai-web`). Tenant isolation
is dual-layer (`TenantManager` + `FORCE RLS` under a restricted role). **New this delta:** account
removal no longer deletes the user row; it disables and scrubs it through per-module
`anonymize_account` handlers (SA216), backed by a test-time personal-data inventory (SA242). One
maintainer; very high cadence; `0.89.0` unpublished.

**Growth direction (planning surface):** Track 1 is SA214 (beta-migration tooling, landing) →
SA191 (`bap-web` rebuild, reseeded) → SA153 (first property portal: Spanish public pages,
listing-linked inquiries into `crm`) → SA204 (migration-history freeze). **Data sensitivity:**
credentials, user PII, Stripe identifiers; no regulatory regime declared, but the product now
makes a user-facing promise ("its personal data removed", `auth/views.py:196`), which activates
lens XVIII this pass. **Cost driver:** flat Railway spend plus bounded Stripe calls.
**Out-of-repo architecture:** Railway proxy/service config, Stripe endpoint versions, the live
`bap-web` database, and PostHog (operator-owned deletion).

**Declared architecture (abridged, unchanged):** modules depend on core, never the reverse; layer
order applies to name references (rule 34), upward needs go through capabilities (rule 4); tenant
data only via `TenantManager` under `FORCE RLS` with a boot guard; clean-break migrations
(`decisions.md` § Clean-Break Migration History); rule 28 file allowlist; rule 33 namespace stem;
every gate registered and in CI parity; templates under `StrictUndefined`; private split modules
never import their facade (SA234).

**Commit delta** `c10b529e..8e4122f2` (~50 non-merge commits, merge-heavy):
- **Closeout:** SA233/SA234 (facade seam), SA235 (manifest UI routes), SA236, SA237, SA238
  (facade trims), SA239, SA240, SA241, SA242 (two tickets sharing the ID in history: the PII
  inventory `54dd3073` and the critical-complexity gate `151f23e2`), SA243 (fixed quality
  thresholds), SA214(a–f) (beta-migration port tooling), SA216(a–c) (anonymize boundary).
- **Housekeeping:** roadmap rebalance/retirement commits, audit re-run commit.
- **Unlabeled-behavioral, read at depth:**
  - `8649849c` — labelled a review round, but it lands the reviewed notification-scrub fix that
    the SA216(a) slice commit left unstaged: the slice commit shipped without it.
  - `6e0ac9da` (SA239, labelled "derive upload extensions") rewrote blog's `0001_initial` to
    reference a **private** field class, `quickscale_modules_blog.models._BlogMediaAssetImageField`
    (`blog/migrations/0001_initial.py:95`). Once SA204 freezes history, that private name is a
    persisted contract (finding 1).
  - `54dd3073` also repaired SA240's closure, which had left the roadmap-consistency gate red.

**Measurements (§3).** Filter: `--no-merges -M`, commits touching > 30 files dropped; lockfiles,
`*.md`, JSON, `module.yml`, version files, and tests excluded.
- **Migration census:** 1 in-place `0001` rewrite in the delta (blog, SA239), down from 22 in the
  prior delta. Still exactly one migration file per model-bearing module (10).
- **Private symbols referenced from migrations:** 1 (above); 0 at `c10b529e`.
- **Personal-data census (new):** the inventory lists **36** fields and **23** exclusions across
  12 app labels; **5** modules declare `anonymize_handlers` (auth, orgs, billing, blog,
  notifications). A year ago: 0 / 0. The inventory's *treatment* column has **0** non-test
  consumers.
- **Split-facade gate scope:** 4 hand-listed `SCAN_ROOTS`
  (`scripts/check_split_facade_imports.py`). SA242 split `beta_migration/project_apps.py` (2,193
  lines removed) into 5 *public-named* files that import each other's `_`-prefixed names, so the
  gate's `_*.py` model does not see them.
- **Quality ledger:** the 55-entry waiver ledger and baseline are deleted (SA243); fixed fail
  lines replace them.
- Ownership: single author throughout.

**Coverage and residual risk.**
- **Read in full:** the SA216 collector (`auth/_anonymization.py`) and its fail-closed owner
  check; the personal-data inventory and its gate; `orgs/checks.py` classification and removal
  checks; module-extension § removal obligations; the SA204 roadmap entry; the SA234 gate header
  and scope; the delta's migration diff.
- **Sampled:** SA214's beta-migration split (imports only); SA243's commit message and gate
  registration; SA235's manifest route declaration.
- **Skipped:** per-module anonymize handler internals (notifications' 503-line scrubber), SA226
  role authorization, SA228 capability registry, SA229 effects, the design-port oracle (SA214(d)).
  **A reader must not conclude they are sound from this document's silence.**
- **Lens activation.** Active: I, II, III, IV, V, VII, VIII, IX, XII, XV, XVI, **XVIII** (new:
  user-facing deletion promise), XIX. Inert: VI, X, XIV (single-process generated apps, no scale
  threshold planned); XVII (no metered driver); XX (one contributor). Archetypes: code generator,
  CLI, multi-tenant. Findings came from I/XVI/XIX (finding 1) and XV/XVIII and the generator
  host-project lens (finding 2).
- **Needs runtime confirmation:** a restored `bap-web` dump against current code (finding 1);
  whether `bap-web`/`experto-ai-web` project apps hold user personal data today (finding 2).
- **Open leads:** none.

## Enforcement census

| Invariant | Where enforced | Posture | Trend since last pass |
|---|---|---|---|
| Tenant reads/writes stay organization-scoped | `TenantManager`, `FORCE RLS`, boot guard; every tenant model on `TenantModel` | Structural | unchanged |
| Project-owned models classified for tenancy | `check_model_classification` (`orgs/checks.py:278`, W005) over project apps at runtime | Structural (runtime check) | unchanged; **contrast row for finding 2** |
| Tenant-module actions authorized by org role | SA226; one org-role check (SA237) | Structural (not audited at depth) | consolidated (SA237) |
| Privileged command set | `runtime/settings.py` + gated copy in `orgs/checks.py` | Structural + gated copy-pair | unchanged |
| Module layer order | import-graph layer test + rule 34 | Gated, closed-world | unchanged |
| Module file names | rule 28 allowlists | Gated, closed-world | unchanged |
| Module options validated | manifest option schema in core (SA217) | Structural | unchanged |
| Split modules don't import their facade | `check_split_facade_imports.py` over 4 hand-listed roots, `_*.py` files only | Gated, open-world on package scope | **new row** (SA234); W8 |
| Quality thresholds | `scripts/check_quality.sh` fixed fail lines (SA242/SA243) | Gated, closed-world per metric | **replaced**: baseline and waivers deleted |
| Declared anonymize obligations executed | `_require_obligation_owners` (`auth/_anonymization.py:72`) fails deletion closed; orgs `E002` | Structural | **new row** (SA216) |
| Every user personal-data field has an anonymize treatment | `test_personal_data_inventory.py` — shipped models only, membership only | Gated (test-time, QuickScale repo only) | **new row**; finding 2 |
| Schema and data survive a QuickScale upgrade | clean-break rule; restore vintage refusal (SA205) | Convention + one refusal gate | unchanged |
| Template ↔ upgradable-code contract | step-identity declarations (SA207/SA211) | Gated | unchanged |
| Org-removal obligations discharged | `AppConfig` declarations + one fail-closed coordinator | Domain-declared, runtime conformance | vocabulary renamed to anonymize (SA216(c)) |
| Stripe API version agrees with SDK pin | runtime refusal; 5 non-test copies | Structural + convention | unchanged (W7) |
| Generator template context complete | `StrictUndefined` + release-lane boot | Structural | unchanged |

## Summary table

| Rank | ID | Title | Horizon | Confidence | Size | Reversibility | Problem in one line |
|---:|---|---|---|---|---|---|---|
| 1 | `clean-break-schema-no-data-path` | Upgrades rewrite schema history with no data carry path | SA153 go-live | High | M | one-way door | Each release may rewrite every module's only migration, and nothing carries a deployed project's data across it. |
| 2 | `personal-data-coverage-shipped-only` | Anonymization completeness is a test-time inventory of shipped models | 6–18 months (first project-owned personal field) | High (mechanism) / Medium (likelihood) | S | two-way door | Detection of unhandled personal data exists only as a QuickScale-repo test over shipped modules; project apps are skipped by design, and the inventory's treatments are tied to no handler. |

## Machine-readable index

```yaml
schema: arch-audit/v9
audited: 8e4122f216824edb62134441a00f2413b3854653
items:
  - {id: clean-break-schema-no-data-path, status: open, rank: 1,
     title: "Upgrades rewrite schema history with no data carry path",
     lenses: [I, XVI, XIX], horizon: sa153-go-live, confidence: High, size: M,
     reversibility: one-way door, depends_on: [], amplifies: [],
     anchors: [docs/technical/decisions.md, docs/technical/roadmap.md,
               quickscale_modules/blog/src/quickscale_modules_blog/migrations/0001_initial.py],
     first_seen: 2026-09-23, last_verified: 2026-10-05}
  - {id: personal-data-coverage-shipped-only, status: open, rank: 2,
     title: "Anonymization completeness is a test-time inventory of shipped models",
     lenses: [XV, XVIII, I], horizon: 6-18-months, confidence: High, size: S,
     reversibility: two-way door, depends_on: [], amplifies: [],
     anchors: [quickscale_modules/orgs/tests/_personal_data_inventory.py,
               quickscale_modules/orgs/tests/test_personal_data_inventory.py,
               quickscale_modules/auth/src/quickscale_modules_auth/_anonymization.py,
               quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py],
     first_seen: 2026-10-05, last_verified: 2026-10-05}
  - {id: W2, status: watchlist, title: "Two filesystem-lock implementations", lenses: [IX]}
  - {id: W3, status: watchlist, title: "Hand-pinned residue in CI provisioning", lenses: [XV]}
  - {id: W4, status: watchlist, title: "trigger_inputs legacy name for an exact allowlist", lenses: [XV]}
  - {id: W6, status: watchlist, title: "Subscription.status has one writing module", lenses: [I]}
  - {id: W7, status: watchlist, title: "Stripe API version literal at five stations", lenses: [VII, XV]}
  - {id: W8, status: watchlist, title: "Split-facade gate scope is hand-listed and file-name keyed", lenses: [XV, III]}
```

---

## Finding 1: Upgrades rewrite schema history with no data carry path

- **ID:** `clean-break-schema-no-data-path`
- **Rank rationale:** High × High, steep. Blast radius is a production tenant database; the
  trigger (SA153 go-live) is on the roadmap. The rewrite rate fell this delta (1 vs 22), but the
  mechanism is unchanged and one rewrite pinned a private symbol into history.
- **Horizon & trigger:** SA153 go-live — the first upgrade of a site holding non-reseedable
  tenant data.
- **Confidence:** High on mechanism (roadmap and migration re-read this pass); Medium on the exact
  runtime symptom.
- **Context dependence:** `wrong-for-now`, keyed on production data; generated-project reality.

**Problem:** each model-bearing module ships exactly one `0001_initial`, rewritten in place when
its schema changes, and no tool carries a deployed project's data from vintage N to N+k.

**Evidence** (re-verified this pass):
- SA204 is still `Deferred`, sequenced after SA153 (`roadmap.md:27`, `:36`); its acceptance text
  (`roadmap.md:121-146`) is unchanged and correct.
- Delta: `6e0ac9da` rewrote `blog/migrations/0001_initial.py:95` in place, swapping
  `models.ImageField` for `quickscale_modules_blog.models._BlogMediaAssetImageField`.
- SA214(f) (`6abdb7a0`) carries **project-owned** app migrations for the one-off SA191 port; it is
  not a module-data carry path and does not change this finding.

**Counter-evidence:** searched decisions, the roadmap, the beta-migration playbook, and SA214's
tooling for a module-data carry plan; found only SA204 (deferred) and SA214's project-app carry.
SA205's restore refusal still contains the restore side.

**Why it compounds:** growth variable is **module schema changes × deployed projects holding
data**. New this pass: migrations can reference private model symbols, so each such reference made
before the freeze becomes a name that can never be renamed or moved afterwards (1 today, 0 before).
Built on top: `bap-web` post-SA191, `experto-ai-web`, every future production project.

**Detection signal:** `InconsistentMigrationHistory` or missing-column `ProgrammingError` during
`start.sh` migrate; SA205's refusal on restore; an `AttributeError` loading a migration after a
private field class is renamed.

**Steelman:** while every deployed database is reseedable, one legible `0001` per module lets
identity-scale renames land with no backfill code. That still holds until SA153.

**Correct shape:** once a project holds production data, a QuickScale upgrade has a verified,
tool-owned path from its recorded vintage to the current one, and frozen history references only
symbols with a stability promise.

**Do-nothing cost:** after SA153's go-live, each module schema change becomes a hand-written ETL
under RLS; the first incident is a failed production deploy.

**Options:**
1. **Freeze at the first production vintage (SA204)** with the hash-manifest gate. **Live.**
2. Vintage-aware logical export/import — relocates the cost into a per-rewrite transform.
3. ~~Accept with restore containment~~ — landed (SA205); revoked at SA153 go-live.

**Recommendation:** option 1, before any post-SA153 module schema change.
- **Size:** `M`. **Reversibility:** `one-way door` — prove `migrate` from the frozen `0001`
  reproduces the RLS parity baseline on a restored `bap-web` copy.
- **Guard:** the SA204 hash-manifest gate, **plus** a check that frozen migrations import no
  `_`-prefixed module symbols (or promote `_BlogMediaAssetImageField` to a public, documented field
  before freezing).
- **First step:** name the freeze release now so SA153 schema work is written as `0002+`.

---

## Finding 2: Anonymization completeness is a test-time inventory of shipped models

- **ID:** `personal-data-coverage-shipped-only`
- **Rank rationale:** Medium × Medium, linear. Blast radius: a user-facing promise ("its personal
  data removed") silently broken for a field nobody declared — one feature family, not a trust
  boundary crossing, and no declared regulatory regime. Likelihood: plausible — SA153's inquiry
  path lands in `crm` (inventoried), but project-owned extension models are the roadmap's
  declared extension model. Compounding: each project-owned or newly shipped personal field adds a
  fixed, unchecked station.
- **Horizon & trigger:** 6–18 months; the first project-owned model with a user relation, email,
  IP, file, or free text on a user-referencing model — or a regulatory obligation (an EU/Spanish
  audience for SA153 makes GDPR erasure plausible).
- **Confidence:** High on mechanism (collector, gate, and checks read; consumers grepped). Medium
  on likelihood (project-app contents of the live sites not inspected).
- **Context dependence:** `wrong-for-now`, dimension: compliance / new domain. Lives in the
  generated-project reality.

**Problem:** the anonymize boundary fails closed only for *declared* obligations; whether every
personal field *has* a declaration is checked by a QuickScale-repo test over shipped models, so
project-owned apps get no detection and the inventory's treatment column is enforced by nothing.

**Evidence** (newly established):
- `auth/_anonymization.py:72-91` (`_require_obligation_owners`) raises only when an app *declared*
  an `ANONYMIZE` obligation without a handler — an undeclared app contributes nothing, silently.
- `orgs/tests/test_personal_data_inventory.py:100-111` (`_shipped_models`) skips every model whose
  module starts with `tests.` and runs only under `orgs/tests/settings.py`; nothing in
  `generator/templates` or any `src/` imports the walk (0 non-test consumers).
- `PersonalDataTreatment` (`_personal_data_inventory.py:30-36`) records SCRUB/DELETE/DELETE_FILE/
  KEEP_LINK per field, but no code compares it with what the handlers do; each module's
  `test_anonymization.py` hand-tests its own handler.
- Contrast: tenancy classification of project-owned models *is* a runtime check
  (`orgs/checks.py:278`, `check_model_classification`, W005) — the repo already owns the pattern.
- Scope note: the inventory defines personal data as *about a user*; visitor PII (e.g. inquiry
  contacts in `crm`) is outside SA216's model entirely.

**Counter-evidence:** searched `orgs/checks.py` (E001–E004, W005), the auth collector, the
module-extension guide, and the generator templates for a runtime or generated-project check over
personal-data fields; found only the declared-obligation check (fail-closed, but declaration-gated)
and the guide's prose telling project apps to declare. The `test_user_fk_conformance.py` gate
covers on-delete rules for user FKs, not anonymization. No out-of-repo control is plausible here.

**Why it compounds:** growth variable is **personal-data fields outside the shipped-module test
harness** (project apps across `bap-web`, `experto-ai-web`, every future project) plus **shipped
fields whose handler drifts from their recorded treatment**. Each needs three hand-synced stations
(inventory entry, `AppConfig` obligation + capability, handler) with only inventory membership
checked, and only for shipped code. Built on top: SA216's account-removal view, 5 handler
modules, and the decision record's "personal data removed" model (`decisions.md:1796`).

**Detection signal:** none today. Instrument: after `anonymize_account`, re-walk candidate fields
for the user and report any non-empty value not marked KEEP_LINK.

**Steelman:** the inventory is two days old and deliberately scoped to what QuickScale ships;
project apps are the operator's code, and the module-extension guide tells them to declare.
With no regulatory regime and few project-owned models, a test is proportionate. Don't fix it
while no generated project holds user personal data outside shipped modules.

**Correct shape:** in every installed project, each candidate personal-data field is classified
(treated or excluded with a reason) by a check that runs where the project's own models are
installed, and the recorded treatment is the thing the handler executes or is verified against.

**Do-nothing cost:** each project-owned personal field is a silent gap in a promise shown to the
user; discovery is an erasure complaint or an audit, and fixing then means scrubbing already
"anonymized" accounts retroactively.

**Options:**
1. **Promote the walk to an orgs system check** (warning like W005, or error once declared), with
   classification declared per app (e.g. a `personal_data_fields()` on `AppConfig` beside
   `removal_obligations`) instead of one central list in orgs' tests. Size S–M; incremental;
   removes the project-app gap and the central hand-list.
2. Add a **post-anonymize verification** test fixture that consumes the inventory's treatment
   column and asserts it on a populated user — removes treatment/handler drift for shipped code
   only. Size S.
3. **Accept and document**: state in decisions that project apps are outside the anonymization
   guarantee; containment is the guide's prose; revocation trigger is a declared regulatory
   obligation or a project-owned user personal field.

**Recommendation:** option 1, with option 2's assertion folded into the per-module tests. It
reuses the W005 pattern this repo already ships and moves ownership of each field's treatment to
the module that owns the field (rule 4's direction).
- **Size:** `S`. **Reversibility:** `two-way door`.
- **Guard:** the system check itself, with controls proving a project-app `EmailField` on a
  user-referencing model fails it.
- **First step:** move `walk_candidate_fields`/`candidate_kinds` from `orgs/tests` into
  `quickscale_modules_orgs` and register it as a warning-level check over project apps.

---

## Change-cost probe

**Probe A: SA191 rebuild `bap-web`** — stations unchanged (facade import in donor
`production.py`, port, project-owned migrations, reseed, verify, deploy + runtime role, recreate
Stripe endpoint, rollback, label/URL-name renames). SA214(c–f) now tools the port, project-app
carry, design layer, and pre-facade settings rewrite: 3 of the 9 stations gained tooling. Data is
still reseeded. **Verdict: finding 1 evidence, narrowed.**

**Probe B: SA153 adds a listing-linked inquiry and a project-owned property model with an
agent contact email.**
1. The inquiry lands in `crm` — already inventoried with treatments. **Exonerated.**
2. The project model's `EmailField` on a model referencing the user: needs an inventory decision,
   an `AppConfig` obligation + `anonymize_handlers` capability, and a handler. Omitting all three
   is detected by **nothing** (the walk skips project apps). **Verdict: finding 2 evidence.**

**Probe C: add a module option** — unchanged since SA217. **Exonerated.**

## Fix-regression audit (closeouts in this delta)

- **SA234 (facade seam):** back-imports removed, `check_split_facade_imports.py` passes (exit 0),
  fail direction preserved (exit 2 on inspection failure). Minted a hand-listed scan scope (W8).
  `split-facades-patch-coupled` stays **closed**.
- **SA242/SA243 (quality gate):** the shrink-only baseline and the 55 split-minted waivers are
  deleted; fixed thresholds have no per-function station to re-key. The prior finding's waiver
  station is **removed, not relocated**. The 800-line fail line will keep forcing splits; SA242's
  own split already landed outside SA234's gate (W8).
- **SA216 (anonymize boundary):** removed the null-out pass and billing detach machinery; declared
  obligations stay fail-closed (sound decision preserved). **Minted** a central, test-only
  personal-data inventory → new finding 2.
- **SA235 (manifest UI routes):** one declaration per module, extends SA223's pattern. Sound.
- **SA237/SA238:** consolidations; no new station observed.

## Fix order and interactions

Independent. Finding 2's check can land any time; finding 1's freeze must precede any post-SA153
module schema change, and if SA153 adds personal fields to shipped modules, those land as `0002+`
migrations *and* inventory entries — doing finding 2 first means the freeze's first migrations are
born classified.

## Sound load-bearing decisions

- **Tenant isolation is dual-layer and fails closed**, every tenant model on `TenantModel`.
- **Removal obligations are app-declared and discharged by one fail-closed coordinator**; SA216
  extended it to anonymize without a second mechanism.
- **Module options and URL/UI routes are declared once in the manifest** (SA217, SA223, SA235).
- **Closed-world module-file allowlists and a module import-layer test.**
- **The generator fails loudly and proves its output boots** (`StrictUndefined`, release-lane
  boot).

## Watchlist

- **W2: two filesystem-lock implementations** (`advisory_lock.py`, `dr_engine/_lock.py`).
  Trigger: a third. **Not fired** — neither changed.
- **W3: hand-pinned residue in `provision_ci_postgres.sh`.** Trigger: a 13th module. **Not
  fired** — 12 modules.
- **W4: `trigger_inputs` legacy name.** Trigger: a skip keyed on it. **Not fired** — the only
  `check_gate_parity.py` change adds `quality` to `_OBSERVED_GATE_NAMES`.
- **W6: `Subscription.status` written only inside billing.** Trigger: a second provider or an
  outside writer. **Not fired** — no writer outside billing.
- **W7: Stripe API version literal at 5 non-test stations** (`_finalize.py:276`, the manifest and
  its mirror, `OPERATIONS.md.j2`, billing README). Trigger: the next Stripe bump. **Not fired.**
- **W8 (new): split-facade gate scope is hand-listed and keyed on `_*.py` names.** SA242 split
  `beta_migration/project_apps.py` into five public-named files importing each other's private
  names, outside the 4 `SCAN_ROOTS`. Fails gate 3 today (one-off devtool, no patch coupling seen).
  Trigger: a product-package split outside the roots, or a test patching a facade path again.

## Rejected candidates

- **SA243's fixed thresholds as a regression of the ratchet:** fixed fail lines are closed-world
  per metric and hold no per-function state; flat cost.
- **SA216's retained user row as an integrity hazard:** retaining the PK keeps attribution and
  removes the null-out pass; operator hard delete still runs rule 27's `SET_NULL`. Sound trade-off.
- **SA214's 1,000+-line carry tooling:** a one-off port tool for SA191 (`devtools`), not a
  generated-project contract; no growth variable.
- Prior rejections (privileged-command copy-pair, conventions harness size, SA223 mounts) —
  unchanged; not re-investigated.

## Questions that would change the ranking

- **`clean-break-schema-no-data-path`:** will `experto-ai-web` migrate too? (Carried; unanswered.)
- **`personal-data-coverage-shipped-only`:** do `bap-web`/SA153 serve an EU audience, or do
  existing project apps hold user personal data? Yes to either promotes it toward rank 1 and
  `now`. (New.)
- The prior question on `generated-file-ownership-unmodeled` ("regenerate and port" as the
  permanent model) is **retired**: SA214 tooled the port as an explicitly one-off path.

*No red flags this pass.*

## Coherence hand-offs

- Anonymization scrubbers range from 56 lines (orgs) to 503 (notifications) with independently
  written escaping logic (`8649849c`'s entity-chain fix lives only in notifications) — a candidate
  for `deep-coherence-audit` on shared scrub helpers.

## Reconciliation log

- 2026-10-05 — `clean-break-schema-no-data-path`: **still-open**, rank 1. One in-place rewrite
  (blog, SA239) that pinned a private symbol; SA204 still deferred after SA153.
- 2026-10-05 — `personal-data-coverage-shipped-only`: **new**, rank 2 — minted by SA216/SA242.
- 2026-10-05 — `split-facades-patch-coupled`: closure **confirmed** by the fix-regression audit
  (gate passes, waiver ledger deleted by SA243); its gate's scope opened W8.
- 2026-10-05 — W2, W3, W4, W6, W7: **carried**, triggers not fired. W8 **opened**.
- 2026-10-05 — Questions: one carried, one opened, one retired. Red flags: none prior, none this
  pass.


- 2026-10-03 — `clean-break-schema-no-data-path`: **still-open**, rank 1. The census grew (22
  rewrites in the delta); SA204 is still deferred after SA153.
- 2026-10-03 — `split-facades-patch-coupled`: **closed** by SA234 (back-imports removed, seam
  gated).
- 2026-10-03 — `split-facades-patch-coupled`: **partly fixed** by SA233 (ratchet keyed by
  qualified name, rename waivers retired); the back-imports remain under SA234.
- 2026-10-03 — `split-facades-patch-coupled`: **new**, rank 2. It was minted by SA231/SA232's
  relocation of god-module coupling into facade back-imports.
- 2026-10-03 — W2, W3, W4, W6, W7: **carried**, triggers not fired (evidence above). W7's station
  list was recounted.
- 2026-10-03 — Enforcement census: the privileged-command row was **corrected** to a gated
  copy-pair.
- 2026-10-03 — Questions: two carried unanswered, one opened. Red flags: none prior, none this
  pass.
- 2026-09-24 — `deletion-invariants-per-boundary-reimplementation`: **resolved** (SA213). Each app
  declares its own removal obligations on its `AppConfig`; `orgs` aggregates the discovered set
  with no vendored labels or fields, both removal boundaries discharge it through one coordinator
  that fails closed on an undischarged obligation, declared provider fields refuse the purge until
  they are cleared or reconciled, app-owned stages run the declaring app's own executor hook, and
  the orgs system check (`E002`) fails a declaration no boundary can route or execute and a
  boundary that stops routing its stages through the coordinator. Archived in CHANGELOG.
- 2026-09-24 — `generated-file-ownership-unmodeled`: **SA211 landed and the finding is closed**
  (merge reconciliation; not audited by this pass). The SA208 provider-ID classification is a
  declared, identified step (`sa208-provider-id-classification` in `orgs`' manifest, mirrored to
  the bundled snapshot), so an upgraded project with an unclassified `*_id` field is refused on
  `apply`/`update`/`deploy railway` until it adopts it. The registered
  `check-project-contract-vintage` gate now fails a module manifest's `contract_vintage` step
  whose text changes without a new id (range, staged, and merge-resolution cases, with controls
  in both directions) and derives its watched template set from
  `get_generator_emission_mapping`, so `pyproject.toml.j2` and `OPERATIONS.md.j2` changes require
  an adoption step. Closed findings leave this file; the prior-pass narrative is in version
  control and the changelog.
- 2026-09-24 — `generated-file-ownership-unmodeled`: **SA207 landed** (merge reconciliation; not
  audited by this pass). One project-level declaration now owns each generated-template contract
  change with its adoption steps, the five SA192 manifest copies, orgs' block, and
  `RAILWAY_CONTRACT_VINTAGE` are gone, applied state records the adopted step ids, `apply`/
  `update`/`deploy railway` refuse on exactly the unadopted steps, confirmation advances the
  recorded vintage, and the registered `check-project-contract-vintage` gate fails a template
  change without a new adoption step id (range, staged, and merge-resolution cases; local, hosted,
  and publish contexts). The finding stays open for what SA211 now carries: step owners, SA208's
  provider-ID step, module-manifest step gating, and a watched set derived from the emission
  manifest.
- 2026-09-24 — `clean-break-schema-no-data-path`: **still-open**, rank 1. No migration changed in
  the delta. SA205 was audited from source: it is sound containment, with a documented bare-file
  edge.
- 2026-09-24 — `generated-file-ownership-unmodeled`: **still-open**, rank 2, blast radius High →
  Medium. SA206 passed the fix-regression audit for code-shaped contracts (mechanism removed,
  fail direction preserved, one deliberate public API minted). New evidence: SA209 added an
  adoption step under an unchanged `minimum`, which the release-granularity gate cannot surface.
  SA207's planned gate is path-enumerated and already misses two template changes in this delta.
  Option 1 struck; option 2 (step identity) is the live recommendation.
- 2026-09-24 — `deletion-invariants-per-boundary-reimplementation`: **still-open**, rank 3.
  Trigger **not fired**. SA208 was audited from source: containment is sound.
- 2026-09-24 — Watch items **W2, W3, W4, W6**: **carried**, triggers not fired (evidence above).
  **W7** opened from SA209.
- 2026-09-24 — Questions: two carried unanswered, one opened.
- 2026-09-24 — Red flags: none prior, none this pass.
- 2026-09-24 — `deletion-invariants-per-boundary-reimplementation`: **containment landed** (SA208,
  option 3). The provider-ID walk runs as an orgs system check over `get_tenant_models()`, and
  purge refuses a provider-backed value.
- 2026-09-23 — `clean-break-schema-no-data-path`: horizon **moved** to SA153's go-live (reseed
  decision). SA205 (`58f58864`) landed the restore vintage refusal.
- 2026-09-23 — `clean-break-schema-no-data-path`: **new**, rank 1.
- 2026-09-23 — `generated-file-ownership-unmodeled`: **regressed** (reopened, rank 2). `882b5cf6`'s
  closure relocated the compounding into hand-copied adoption prose. SA206 then implemented option
  1.
- 2026-09-23 — `deletion-invariants-per-boundary-reimplementation`: **still-open**, rank 3. Prior
  counter-evidence corrected, and the trigger gained a project-provider-ID clause.
- 2026-09-23 — **W1** (privileged command set, five stations): **superseded** by
  `generated-file-ownership-unmodeled`. The station has since collapsed into the facade (SA206).
- 2026-09-23 — **W5** (hand-authored ownership taxonomy): trigger **fired**. **Superseded** by
  `generated-file-ownership-unmodeled`.
- 2026-09-23 — W2, W3, W4 carried; W6 opened. Probe A cleanup resolved by SA195. Red flags: none.
- 2026-09-23 — `module-env-contract-hand-wired`: **resolved** (declaration-driven `.env.example`
  renderer plus conformance); archived in CHANGELOG.
- 2026-09-18 — `deletion-invariants-per-boundary-reimplementation`: **still-open** (SA190 made the
  inventory structural).
- 2026-09-17 — `module-env-contract-hand-wired`: **new**, rank 1. W1–W5 established or carried.
  No red flags; a `compare_digest` defect was found already fixed (`adc753c6`).
