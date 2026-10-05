# Structural Autopsy: QuickScale

Audited: `e2623cb8` (`v89`) · 2026-10-05 · working tree clean · prompt: deep-architectural-audit v9

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

**Commit delta** `8e4122f2..e2623cb8` (6 non-merge commits):
- **Closeout:** SA246 (`2f1d0a4e`, `db0fcc55`: per-app `personal_data_declarations` capability,
  W006 over project models), SA244 (`b179990b`: anonymization scoped to the person's records,
  bounded scans), SA247 (`fe5d808a`, `7969c59b`: module-conventions harness split into
  `scripts/module_conventions/` and `scripts/tests_module_conventions/`, behavior unchanged).
- **Housekeeping:** `d08f513c` (roadmap/audits), `467ced81` (contract doc wording).
- **Unlabeled-behavioral, read at depth:** none by message, but `b179990b` (SA244) mints a
  cross-module contract its message calls a scoping fix: the orgs invitation send now stamps an
  `actor_user_id` key into notification context (`orgs/views.py:200`), and notifications'
  anonymizer selects on it (`notifications/_anonymization.py:146`). That key appears in no
  signature, doc, or gate → new finding 2.

**Measurements (§3).** Filter: `--no-merges -M`, commits touching > 30 files dropped; lockfiles,
`*.md`, JSON, `module.yml`, version files, and tests excluded.
- **Migration census:** 0 module migration rewrites this delta (1 prior, 22 before that); the
  only new migration is the test project app's `0002_projectlisting_contact_email.py`. Still exactly one migration file per model-bearing module (10).
- **Private symbols referenced from migrations:** 1 (`blog/migrations/0001_initial.py:95`, re-verified).
- **Personal-data declarations:** now collected per app (SA246); the central test-only inventory
  file (485 lines) is deleted, and W006 consumes the treatments at runtime.
- **Notification senders** (`send_notification` callers outside notifications): **2** (orgs
  invitations, forms submissions); **1** stamps `actor_user_id`. One year ago: 0 (module did not
  exist at that revision).
- **SA247 split:** `check_module_conventions.py` 6,731 → 187 lines over 13 package files under
  `scripts/`, outside the split-facade gate's 4 `SCAN_ROOTS`; tests import through the facade
  (`from scripts import check_module_conventions as checker`) and patch nothing through it.
- **Split-facade gate scope:** 4 hand-listed `SCAN_ROOTS`
  (`scripts/check_split_facade_imports.py`). SA242 split `beta_migration/project_apps.py` (2,193
  lines removed) into 5 *public-named* files that import each other's `_`-prefixed names, so the
  gate's `_*.py` model does not see them.
- **Quality ledger:** the 55-entry waiver ledger and baseline are deleted (SA243); fixed fail
  lines replace them.
- Ownership: single author throughout.

**Coverage and residual risk.**
- **Read in full this pass:** SA246's `_personal_data.py` header and gap functions, the W006 check,
  the core declaration records; SA244's diff; notifications' message selector; forms' sender.
- **Read in full (prior pass):** the SA216 collector (`auth/_anonymization.py`) and its fail-closed owner
  check; the personal-data inventory and its gate; `orgs/checks.py` classification and removal
  checks; module-extension § removal obligations; the SA204 roadmap entry; the SA234 gate header
  and scope; the delta's migration diff.
- **Sampled:** SA214's beta-migration split (imports only); SA243's commit message and gate
  registration; SA235's manifest route declaration.
- **Skipped:** per-module anonymize handler internals (notifications' 503-line scrubber), SA226
  role authorization, SA228 capability registry, SA229 effects, the design-port oracle (SA214(d)).
  **A reader must not conclude they are sound from this document's silence.**
- **Lens activation.** Active: I, II, III, IV, V,   VII, VIII, IX, XII, XV, XVI, **XVIII** (new:
  user-facing deletion promise), XIX. Inert: VI, X, XIV (single-process generated apps, no scale
  threshold planned); XVII (no metered driver); XX (one contributor). Archetypes: code generator,
  CLI, multi-tenant. Findings came from I/XVI/XIX (finding 1) and III/VII/XVIII (finding 2).
- **Needs runtime confirmation:** a restored `bap-web` dump against current code (finding 1).
- **Needs runtime confirmation:** whether any deployed project already holds pre-key invitation
  messages (finding 2's recorded limit).
- **Open leads:** none.

## Enforcement census

| Invariant | Where enforced | Posture | Trend since last pass |
|---|---|---|---|
| Tenant reads/writes stay organization-scoped | `TenantManager`, `FORCE RLS`, boot guard; every tenant model on `TenantModel` | Structural | unchanged |
| Project-owned models classified for tenancy | `check_model_classification` (`orgs/checks.py:278`, W005) over project apps at runtime | Structural (runtime check) | unchanged |
| Tenant-module actions authorized by org role | SA226; one org-role check (SA237) | Structural (not audited at depth) | consolidated (SA237) |
| Privileged command set | `runtime/settings.py` + gated copy in `orgs/checks.py` | Structural + gated copy-pair | unchanged |
| Module layer order | import-graph layer test + rule 34 | Gated, closed-world | unchanged |
| Module file names | rule 28 allowlists | Gated, closed-world | unchanged |
| Module options validated | manifest option schema in core (SA217) | Structural | unchanged |
| Split modules don't import their facade | `check_split_facade_imports.py` over 4 hand-listed roots, `_*.py` files only | Gated, open-world on package scope | unchanged; SA247 split landed outside it (W8) |
| Quality thresholds | `scripts/check_quality.sh` fixed fail lines (SA242/SA243) | Gated, closed-world per metric | **replaced**: baseline and waivers deleted |
| Declared anonymize obligations executed | `_require_obligation_owners` (`auth/_anonymization.py:72`) fails deletion closed; orgs `E002` | Structural | **new row** (SA216) |
| Account anonymization reaches every notification about a person | `actor_user_id` context key stamped by each sender (1 of 2) + address fallback | Convention, ungated | **new row** (SA244); finding 2 |
| Every personal-data field has a declared anonymize treatment | each app's `personal_data_declarations` capability; `test_personal_data_inventory.py` (closed-world) and `check_personal_data_declarations` (W006) over project apps | Structural + gated (runtime warning + closed-world test) | verified this pass (SA246 fix-regression audit passed) |
| Schema and data survive a QuickScale upgrade | clean-break rule; restore vintage refusal (SA205) | Convention + one refusal gate | unchanged |
| Template ↔ upgradable-code contract | step-identity declarations (SA207/SA211) | Gated | unchanged |
| Org-removal obligations discharged | `AppConfig` declarations + one fail-closed coordinator | Domain-declared, runtime conformance | vocabulary renamed to anonymize (SA216(c)) |
| Stripe API version agrees with SDK pin | runtime refusal; 5 non-test copies | Structural + convention | unchanged (W7) |
| Generator template context complete | `StrictUndefined` + release-lane boot | Structural | unchanged |

## Summary table

| Rank | ID | Title | Horizon | Confidence | Size | Reversibility | Problem in one line |
|---:|---|---|---|---|---|---|---|
| 1 | `clean-break-schema-no-data-path` | Upgrades rewrite schema history with no data carry path | SA153 go-live | High | M | one-way door | Each release may rewrite every module's only migration, and nothing carries a deployed project's data across it. |
| 2 | `notification-person-link-by-convention` | Notification ↔ person link is an unstamped-by-default context key | SA153 | Medium | S | two-way door | Anonymization finds a person's notifications through a context key each sender must remember to stamp, so every new sender can silently fall outside the deletion promise. |

## Machine-readable index

```yaml
schema: arch-audit/v9
audited: e2623cb8bb727d177c337d1431db40e134dcfaf0
items:
  - {id: clean-break-schema-no-data-path, status: open, rank: 1,
     title: "Upgrades rewrite schema history with no data carry path",
     lenses: [I, XVI, XIX], horizon: sa153-go-live, confidence: High, size: M,
     reversibility: one-way door, depends_on: [], amplifies: [],
     anchors: [docs/technical/decisions.md, docs/technical/roadmap.md,
               quickscale_modules/blog/src/quickscale_modules_blog/migrations/0001_initial.py],
     first_seen: 2026-09-23, last_verified: 2026-10-05}
  - {id: notification-person-link-by-convention, status: open, rank: 2,
     title: "Notification-to-person link is a convention-stamped context key",
     lenses: [III, VII, XVIII], horizon: sa153, confidence: Medium, size: S,
     reversibility: two-way door, depends_on: [], amplifies: [],
     anchors: [quickscale_modules/notifications/src/quickscale_modules_notifications/services.py,
               quickscale_modules/notifications/src/quickscale_modules_notifications/_anonymization.py,
               quickscale_modules/orgs/src/quickscale_modules_orgs/views.py],
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

## Finding 2: Notification-to-person link is a convention-stamped context key

- **ID:** `notification-person-link-by-convention`
- **Rank rationale:** Medium × Medium, linear. Blast radius is the user-facing deletion promise
  (one module's records); SA153 plausibly adds inquiry/agent notifications; each new sender adds a
  fixed chance of a silent miss.
- **Horizon & trigger:** SA153 — the first new `send_notification` caller that renders a user's
  name without their address.
- **Confidence:** Medium. Mechanism read in code and senders censused (2); whether a real sender
  renders a name without an address is inferred, not observed beyond the invitation case.
- **Context dependence:** `wrong-for-now` (privacy promise); generated-project reality.

**Problem:** the only structural link from a stored notification to the person it is *about* is
an `actor_user_id` key inside free-form `context_json`, which each caller must remember to stamp;
`send_notification` has no parameter, column, or check for it.

**Evidence** (newly established):
- `notifications/services.py:86-94` — `send_notification(*, template_key, recipients, context,
  tags, metadata, mailer)`: no subject/actor argument.
- `notifications/_anonymization.py:144-147` selects `context_json__actor_user_id=str(user.pk)`;
  module docstring `:12`: "an `actor_user_id` key that `send_notification` callers stamp".
- Census: 2 callers outside notifications; **1** stamps it (`orgs/views.py:200`); forms
  (`forms/_email.py:104`) does not, relying on the address fallback.
- The docstring records the limit already: pre-key invitations "stay as stored".
- `grep actor_user_id docs/` → 0 hits: the rule is in no Module Conventions rule or extension doc.

**Counter-evidence:** searched the conventions harness (`scripts/module_conventions/`), W006
(`orgs/checks.py`), `module-extension.md`, and SA245's roadmap entry for a rule or gate requiring
senders to declare the person; found none. W006 checks *model fields*, so a name inside JSON is
invisible to it. Partial mitigation: the address fallback catches any message whose context holds
the person's complete address.

**Why it compounds:** growth variable is **notification senders** (shipped modules and project
apps; `send_notification` is public). Each one that renders a person by name or username alone and
forgets the key leaves that text behind after "its personal data removed", with no failing signal.
Built on top: orgs invitations, SA244's selector, SA245's planned shared matcher.

**Detection signal:** none today. Instrument: count, per template key, messages lacking both
`actor_user_id` and a recipient delivery; or a test that renders each registered template with a
sentinel user and asserts the anonymizer selects it.

**Steelman:** most senders put the person's address in context, which the fallback catches; the
invitation is the one known name-only case and it is stamped. Accept while the sender set stays
at two shipped modules and no project app sends notifications.

**Correct shape:** the persons a message is about are declared at the send boundary (a required
argument or a template-level declaration) and stored where the anonymizer reads them, so a sender
cannot omit the link silently.

**Do-nothing cost:** each new sender needs someone to know an undocumented key; a miss is a
retained name discovered only by a user complaint.

**Options:**
1. **Promote the key to a keyword argument** (`about_users=`) of `send_notification`, stored on
   the message (column or reserved context key written by notifications itself); required-or-empty
   explicit. S, incremental, removes the convention.
2. Declare per template key which context fields name a user (template registry metadata);
   anonymizer derives the selector. M; also covers name-only fields.
3. **Accept and document** in Module Conventions with a harness rule flagging `send_notification`
   calls without the key; revoke at SA153.

**Recommendation:** option 1, folded into SA245 since it edits the same handler.
- **Size:** `S`. **Reversibility:** `two-way door`.
- **Guard:** the keyword is required (no default), so every caller states it; a conventions rule
  fails a direct `context_json` write of the key.
- **First step:** add the keyword and have orgs pass it instead of stamping context.

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
2. The project model's `EmailField` on a model referencing the user: needs a declared treatment
   (or reasoned exclusion) on the app's `personal_data_declarations` capability, and for a
   treatment other than `KEEP_LINK` an `anonymize_account` executor with `anonymize_handlers`.
   Omitting the declaration now warns at runtime (`W006`) and fails the closed-world test.
   **Exonerated by SA246.**
3. An "inquiry received" email to the agent naming the inquirer: a new `send_notification`
   caller; nothing requires stating whom it is about. **Verdict: finding 2 evidence.**

**Probe C: add a module option** — unchanged since SA217. **Exonerated.**

## Fix-regression audit (closeouts in this delta)

- **SA246 (personal-data declarations):** the central test-only inventory is deleted; each app
  declares its rows on its own `AppConfig`, and W006 walks project models where installed
  (`_personal_data.py:217-231`). Mechanism **removed, not relocated**. Fail direction: warning-only
  by design (startup must not block), with the closed-world test as the hard gate for shipped
  modules. Minted: core now hosts the declaration records (`runtime/conventions.py`) — a generic
  type at the lowest layer, the correct dependency direction. W006 checks that a handler *exists*
  for a declared treatment, not that it executes each row; per-module tests cover that for
  shipped modules. `personal-data-coverage-shipped-only` stays **resolved**.
- **SA244 (anonymization scoping):** the over-broad selectors are gone and scans are bounded.
  **Minted** the `actor_user_id` convention → new finding 2.
- **SA247 (harness split):** behavior-preserving; devtool, outside product packages; no facade
  patching in tests. No new structural commitment beyond W8's existing note.

## Fix order and interactions

Finding 2 is independent of finding 1 and should ride SA245 (same file). Finding 1's freeze must precede any post-SA153 module schema change, and if SA153
adds personal fields to shipped modules, those land as `0002+` migrations *and* declaration
entries, so the freeze's first migrations are born classified.

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
  Trigger: a third. **Not fired** — neither changed (`git diff 8e4122f2..HEAD` empty).
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
  **Not fired** — SA247's split is under `scripts/` (devtool) and its tests patch nothing through
  the facade.

## Rejected candidates

- **Core owning personal-data vocabulary (SA246) as a layer inversion:** the records are
  generic types consumed by modules, not module-specific words; the direction is correct.
- **W006 being warning-only:** deliberate (must not block startup); the closed-world test is the
  hard gate for shipped code, and project apps get a visible warning. Steelman holds.

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
- The prior question on `generated-file-ownership-unmodeled` ("regenerate and port" as the
  permanent model) is **retired**: SA214 tooled the port as an explicitly one-off path.

*No red flags this pass.*

## Coherence hand-offs

- Anonymization scrubbers' independently written escaping logic — **now scheduled as SA245**;
  carried here until it lands.

## Reconciliation log

- 2026-10-05 (pass 2, `e2623cb8`) — `clean-break-schema-no-data-path`: **still-open**, rank 1.
  No module migration changed; private-symbol reference re-verified.
- 2026-10-05 (pass 2) — `notification-person-link-by-convention`: **new**, rank 2, minted by SA244.
- 2026-10-05 (pass 2) — `personal-data-coverage-shipped-only`: resolution **confirmed** by the
  fix-regression audit.
- 2026-10-05 (pass 2) — W2, W3, W4, W6, W7, W8: **carried**, triggers not fired.
- 2026-10-05 (pass 2) — Questions: one carried. Red flags: none prior, none this pass. Coherence
  hand-off (shared scrub helpers) is now scheduled as SA245.

- 2026-10-05 — `clean-break-schema-no-data-path`: **still-open**, rank 1. One in-place rewrite
  (blog, SA239) that pinned a private symbol; SA204 still deferred after SA153.
- 2026-10-05 — `personal-data-coverage-shipped-only`: **closed** by SA246 (per-app
  `personal_data_declarations` capability; `walk_candidate_fields`/`candidate_kinds` run as the
  W006 warning over project-owned models; per-module tests assert the declared treatments; the
  closed-world inventory test reads the collected declarations and keeps its three controls).
  Archived in CHANGELOG.
- 2026-10-05 — `split-facades-patch-coupled`: closure **confirmed** by the fix-regression audit
  (gate passes, waiver ledger deleted by SA243); its gate's scope opened W8.
- 2026-10-05 — W2, W3, W4, W6, W7: **carried**, triggers not fired. W8 **opened**.
- 2026-10-05 — Questions: one carried, one retired. Red flags: none prior, none this
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
