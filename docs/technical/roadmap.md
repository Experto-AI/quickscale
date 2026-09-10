# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Ticket context](v88_ticket_context.md) | [Changelog](../../CHANGELOG.md)

## Goal and release finish line

Ship the v88 hardening release with working generated-project writes and accepted retained
hardening. Then deliver the first useful property portal in a
project-owned extension, generalizing capabilities only after that project proves their value.

The v88 hardening release had a root-finalized green candidate and release aggregate before terminal
attestation exposed CSRF integration defects. A retained terminal-remediation commit corrected the
token bootstrap and duplicate-cookie implementation, tests, generated hashes, and status. The
corrected candidate at `cb21f791826c9ebcfdba5f8b034d7eddef8e02df` was independently reviewed and its
single authorized `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` attempt reached the final E2E stage but
returned exit 2: Core reported 38 passed and 1 failed in the generated production browser proof,
while CLI reported 54 passed. The prior green aggregate is historical evidence for prior bytes; this
red result leaves the corrected work below release acceptance and non-mergeable. No retry is
authorized by the spent exact-once authority. Merge, release-note/version checks, tagging,
publishing, and deployment remain separate maintainer actions.

The same candidate also retains a high-severity client-identity divergence. The shared
`quickscale_modules_orgs.current_org.get_client_ip` resolver falls back to `REMOTE_ADDR` when the
normalized `X-Forwarded-For` chain is shorter than `TRUSTED_PROXY_COUNT`, while ordinary DRF
throttles configured through `NUM_PROXIES` select an `X-Forwarded-For` entry from that same short
chain. Every consumer must share one fail-closed contract: shorter chains use `REMOTE_ADDR`, equal
and longer chains select the same right-indexed client hop, empty hops cannot satisfy the trusted
proxy count, and missing or invalid proxy settings fail loudly. Both this security boundary and the
red browser proof must close before merge. Correcting or rerunning only the browser failure cannot
authorize merge.
Optional maintenance may move past the release without delaying it.

The scheduling table holds currently authorized work and owns horizon, track, dependencies, and
release requirement. A blocked continuation checkpoint may remain under v88 deliveries until its
next action is authorized; it is not an open schedule entry by itself. Ticket bodies own scope and
acceptance; [context](v88_ticket_context.md) explains implementation concepts;
[CHANGELOG.md](../../CHANGELOG.md) preserves history and evidence. Absorbing a ticket transfers its
unfinished obligations and does not claim its finding is fixed.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA152 | Verify maintainer migration modes and their runtime compatibility | post-v88 | 2 | — | Deferred |
| SA180 | Derive the gate-parity count oracles from the registry | post-v88 | 2 | — | Deferred |
| SA177 | Verify the predicates of enrolled RLS policies | post-v88 | 3 | — | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | — | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |

Track numbers map to the existing worktrees: **1 = W1 / wt-track1**, **2 = W2 / wt-track2**,
**3 = W3 / wt-track3**. Post-v88 assignments identify future ownership, not authorization to
start them during release work. SA154 is an inventory, not an implementation queue.

```text
Track 1: (no currently authorized v88 ticket)
Track 2: (idle in v88)      owns post-v88 SA152, SA180
Track 3: (idle in v88)      owns post-v88 SA177
```

**Release recovery requires two independent closures: client-identity parity and a green genuine-
HTTPS production-browser proof.** Reconcile the shared `get_client_ip` resolver, the forms throttle
override, blog/forms persistence, and every ordinary DRF throttle using `NUM_PROXIES` to one tested
contract: a shorter normalized forwarding chain must fail closed to `REMOTE_ADDR` for every
consumer; equal and longer chains must resolve the same right-indexed client hop; empty hops must not
inflate the chain; and missing or invalid proxy counts must fail loudly. Separately diagnose and
correct the test-only HTTPS proxy/navigation failure, complete the real `apiRequest` mutation proof,
and pass the owning task tier. The retained release attempt ended red before the positive mutation
assertion and consumed its exact-once authority, so a newly reviewed candidate and fresh release
authority are required. A browser-only correction, task pass, or green release rerun cannot authorize
merge while client-identity parity remains open. All tracks stay idle for v88; their post-v88
assignments are future ownership, not release work.

Post-v88 ordering: SA177 may take the isolation runner freely now that SA165 has closed.
SA152 and SA153 are independent — the portal can use a fresh generated project — though a
real-site cutover through the beta-migration tools would make SA152 a cutover prerequisite. SA154
follows the working portal, and SA180 owns the gate files SA152 also touches.

### Track states

Each track reports three independent states. A track is **truly green** only when all three
are yes.

| Track | Ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | — | n/a — no authorized v88 ticket | n/a | n/a | n/a | no |
| 2 | — | n/a — no v88 ticket | n/a | n/a | n/a | no |
| 3 | — | n/a — no v88 ticket | n/a | n/a | n/a | no |

All originally scheduled implementation phases reached acceptance before terminal attestation. The
single green release aggregate, successful exact-scope cleanup, and standing-resource preservation
remain historical evidence for the pre-remediation bytes only. The retained remediation's owning
`make test-unit -- --core` task tier passed before its one fresh release attempt returned red in Core
E2E. The corrected candidate is not release-accepted or merge-ready.

### Ownership and merge coordination

- Track 1 has no currently authorized v88 ticket; its post-v88 ownership remains SA153 and SA154.
- Track 2 owns gate documentation, `scripts/gate_registry.json` and module declarations, and the
  maintainer migration tools. It holds no v88 work; SA152 and SA180 are post-v88.
- Track 3 owns deferred predicate conformance under SA177, including the isolation runner.
- Product implementation stays in worktrees, with one delivery candidate at a time per track and
  one serialized merge queue into `v88`. Independent work does not wait for another track's audit
  markdown edits. Reconcile shared documentation at merge time on the owning worktree.
- **Conflict surface.** The cross-track shared closeout set is this roadmap,
  [CHANGELOG.md](../../CHANGELOG.md), [ticket context](v88_ticket_context.md) when concepts change,
  and the owning audit. Every one of them is Markdown with append-or-edit
  semantics and no generated consumer, and the serialized merge queue plus reconcile-on-the-owning-
  worktree rule above covers them: each track resolves the shared set once, at its own merge, after
  the previous merge has landed. The consistency test then checks structure, not status prose.
  No track currently has authorized v88 work, so the shared closeout set has no active v88 writer.
- The retained SA160 checkpoint's conditional Docker-backed release authority was consumed by the
  recorded red result. A future attempt requires a newly reviewed candidate and distinct authority
  after both the client-identity divergence and browser-harness failure are corrected.
  Future Docker-heavy work follows the
  [execution policy](validation_policy.md#candidate-review-and-integration) for routing, cleanup,
  candidate binding, and review/merge rules.

### Resuming a track

Measure state; do not read it from this planner. Check the assigned branch, divergence from `v88`,
staged/unstaged changes, untracked files, and any merge in progress, then read the diffs and prior
evidence before deciding anything is blocked. A dirty worktree is a recovery step, not a stop
condition: cleanliness is required for the frozen review and the merge, never for inspection or
for continuing understood, in-scope edits. A shared filename alone is a merge concern; a changed
input to an active reviewed candidate is a real dependency.

Preserve before you reconcile. Stage an explicit reviewed file list and make a clearly labeled
WIP checkpoint for work that would otherwise be lost — a checkpoint is not acceptance and must not
enter `v88` as a completed delivery. Never sweep unrelated work in with `git add .`, never
auto-drop a stash, and never use destructive reset or checkout to manufacture a clean status.
Then merge `v88` into the worktree, resolve conflicts there, run the consistency suite, and
continue the task's own validation. Merge only the reviewed and accepted delivery, through the
serialized queue. Stop only at a concrete unresolved ownership conflict, missing authority, or
failed prerequisite, naming the affected files and action.

Each outgoing handoff records the task, inspected diff, checkpoint or stash identity, remaining
changes, conflicts, evidence obtained, and the exact next command. Keep that record in the handoff
or delivery evidence, not here.

## v88 deliveries

### SA160 release attempt — Core E2E red in the generated browser proof

  **State (measured 2026-09-10):** corrected candidate `cb21f791826c9ebcfdba5f8b034d7eddef8e02df`
  is retained and unmerged on `wt-track1`; integration ref `v88` remains
  `5716dabfc9d2d90eda69fe62a934c36567e9ec16`. An independent review covered the exact 20-path
  candidate before the single authorized release attempt. This is red release evidence, not an
  accepted product candidate or release. No retry, merge, publication, tag, or deployment occurred.

  The candidate also retains a client-identity security-boundary mismatch. The shared
  `get_client_ip` resolver used by the forms throttle override and blog/forms persistence returns
  `REMOTE_ADDR` for a normalized forwarding chain shorter than `TRUSTED_PROXY_COUNT`; ordinary DRF
  throttles configured through `NUM_PROXIES` can instead trust an entry from that short chain. The
  candidate therefore remains non-mergeable independently of the browser failure.

  **Completed:** the earlier retained remediation still preserves the production HttpOnly CSRF cookie,
  masked shell token, Django-last duplicate-cookie behavior, both generated callers, and three rebound
  emission variants. The corrected candidate also aligns the stale shell assertion and provides a
  generated production browser harness covering strict install, migrate, cache-table creation,
  frontend type-check/build, collectstatic, credential creation, production server startup, an
  unproxied HTTPS-redirect control, secure-cookie calibration, omitted-header rejection, and the
  intended `OrgCreatePage` → `useCreateOrg` → `apiRequest` mutation. Stages 1–11 passed, including
  5,093 Core/CLI coverage tests with 2 skips, 332 backups tests with 1 skip, and the full module
  integration stage. Stage 12's CLI lane passed 54 tests; Core reported 38 passed and 1 failed in
  `test_production_shell_csrf_token_accepts_authenticated_org_mutation` at
  `quickscale_core/tests/test_generated_project_runtime.py:2209`, where Chromium returned
  `net::ERR_TOO_MANY_RETRIES` for the HTTPS proxy navigation and the proxy logged `BrokenPipeError`.

  **Pending:** reconcile the shared resolver, the forms throttle override, blog/forms persistence,
  and every ordinary DRF throttle using `NUM_PROXIES` to one fail-closed identity contract. Pin
  shorter, equal, and longer normalized forwarding chains across every consumer: shorter chains use
  `REMOTE_ADDR`; equal and longer chains select the same right-indexed client hop; empty hops cannot
  inflate the chain; and missing or invalid proxy settings fail loudly. Also diagnose and correct the
  test-only HTTPS proxy/navigation failure without weakening shipped redirect, Secure, HttpOnly,
  proxy, or CSRF semantics. The positive browser assertions must complete without injected session
  cookies or positive CSRF headers, and the focused node must pass with no skip. Both corrections
  require a fresh reviewed candidate and fresh release authority; the current exact-once authority
  is spent and cannot be retried.

  **Blocking:** two independent blockers prohibit release and merge acceptance. At the client-
  identity seam, a one-entry normalized `X-Forwarded-For` chain with
  `TRUSTED_PROXY_COUNT=2` resolves to `REMOTE_ADDR` through the shared resolver but to the forwarded
  entry through ordinary DRF throttling; request throttling, persistence, and audit identity can
  therefore diverge on caller-controlled input. In the generated production browser proof, Chromium
  could not complete navigation to `https://localhost:<proxy>/orgs/new/`, returning
  `net::ERR_TOO_MANY_RETRIES`; the test proxy recorded a `BrokenPipeError` while writing the upstream
  response. The Core lane returned 38 passed / 1 failed and the aggregate returned exit 2. The browser
  failure is not covered by an accepted-failure oracle, and no second aggregate is authorized.

  **Decisions needed:** authorize a new reviewed candidate that closes both the every-consumer
  client-identity contract and the diagnosed browser proxy failure, followed by a fresh release
  attempt. Correcting or rerunning only the browser failure cannot authorize merge. Trusted-origin
  overrides, injected cookies or CSRF headers, and weakened production security settings remain
  unacceptable substitutes.

  **Remaining plan:** retain the exact red evidence referenced by the changelog; make the shared
  resolver, forms override, blog/forms persistence, and ordinary DRF throttles agree on fail-closed
  shorter-chain and matching equal/longer-chain identity, with empty-hop and invalid-setting negative
  controls; correct the test-only proxy failure without weakening product security; re-run the
  focused and owning task-tier checks; independently review the new exact tip; and obtain fresh
  release authority. A browser-only correction or rerun is insufficient for merge. The current
  candidate remains unmerged; red evidence stays unmerged and no aggregate retry is permitted.

## Post-v88 work

- [ ] **SA152 — Verify maintainer migration modes and their runtime compatibility.**

  Includes former SA175. Compare outcomes within each migration mode, not membership in constants
  from different modes. Donor-carried `settings/production.py` and substituted infrastructure may
  be intentional; a blanket assertion rejecting that arrangement while preserving it cannot be
  the acceptance condition.

  **Acceptance:** name the launcher/settings contract once and derive each mode's effective file
  sources for `settings/production.py`, `start.sh`, and `Dockerfile`. Preserve the accepted donor
  precedence. Exercise compatible and deliberately incompatible file combinations in isolated
  fixtures through the existing validation seam, proving the compatible contract passes and an
  unsupported privileged-command/runtime combination fails for the intended reason. Do not turn
  an expected file classification into a claim of runtime compatibility.

  In the same smoke suite, run fresh-first dry-run and in-place checkpoint-only workflows on a
  generated donor/recipient pair, without modifying a real project or database. Reconcile the
  in-place database precondition with the fresh-database migration policy. Replace missing-template
  `pytest.skip()` with a tested explicit failure. Register the smoke gate in the existing registry,
  keep gate parity green, and correct the migration playbook's version/location claims. Retire only
  discharged findings; the broader ownership-model finding remains behind its growth triggers.

  **Surfaces:** `quickscale_devtools/.../beta_migration.py`, CLI ownership/migration tests, existing
  gate registry and parity wiring, Make/CI entrypoints as needed, and migration playbook. No public
  updater, typed ownership framework, or changed file precedence is included.

- [ ] **SA180 — Derive the gate-parity count oracles from the registry.**

  The architecture audit confirmed this trigger **fired** — `d31c6b41` and `437dd0e0` each crossed
  the written more-than-two-edit threshold on hand-pinned count literals. The closed documentation
  pass corrected the descriptions; correcting wording does not and cannot discharge the finding, so
  it is owned here rather than left as an unassigned note in the audit.

  **Acceptance:** compute the count-pinned gate-parity oracles from the registry and workflow
  sources they describe, so adding a gate or station cannot leave a stale literal behind. Keep the
  closed-universe check and the existing failure messages loud. Prove with a regression that adding
  a gate updates the derived count without a hand edit. Retire the count-pinned watch item only
  with that evidence. Renaming `trigger_inputs` stays out of scope: the field is the settled name for the
  bidirectional `e2e.yml` allowlist partition, and only a skip-based use would reopen it.

  **Surfaces:** `scripts/check_gate_parity.py`, `scripts/test_gate_parity.py`,
  `scripts/gate_registry.json` if a derivation source is needed, and the architecture audit.

- [ ] **SA177 — Verify the predicates of enrolled RLS policies.**

  **Acceptance:** walk enrolled tables and compare both policies' stored `qual` and `with_check`
  expressions in `pg_policies` against the rendered expected policies, accounting for PostgreSQL's
  catalog representation. A deliberately weakened predicate must fail for the intended reason;
  restore the exact policy after the negative control. Preserve tenant-write/operator-read
  semantics and existing RLS boundary checks. Retire the predicate-conformance tooling gap only
  after this proof. Reassess priority if later work changes policy semantics before this lands.

  **Surfaces:** isolation-conformance runner, orgs policy template/tests, and technical audit.

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target the planned `buenosairesproperties.com` use case with one Django-rendered public surface.
  Use the documented project-owned extension pattern for property models, views, URLs, filters,
  and templates. Do not require a public JSON API, a second React public implementation, or generic
  property behavior in every generated project to launch the first site.

  **Acceptance:** a fresh generated project with listings serves an organization-scoped property
  catalog and detail page with ordered image galleries; bedrooms, bathrooms, area, property type,
  and sale/rent fields; keyword and attribute filters; and explicitly labeled currencies. Its
  public listing/blog pages share a usable theme and render in Spanish, with locale middleware
  and translated strings needed by this public flow. A listing inquiry creates a CRM record with
  a listing reference. Add sitemap entries, `robots.txt`, and Open Graph output for the public
  detail pages. Correct reusable-module feature claims to match what the module itself provides.

  Every new tenant-owned child table has its own `organization_id`, forced RLS, and boundary tests;
  no parent-join policy replaces that requirement. Prove the user journey from search through
  detail to inquiry, and isolation between organizations. Keep property-specific glue in the
  project extension and avoid direct edits to embedded module code. Validate any required shared
  extension seam narrowly. A real-site data cutover requires a verified data/migration path and
  explicit deployment scope; building this delivery does not authorize production mutation.

  **Surfaces:** project-owned property extension and public templates first; listings/blog/forms/CRM
  seams only where necessary, plus extension documentation. Broad module translation and generic
  no-project-glue integration are deferred until reuse demonstrates a need.

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: public read API and an alternate frontend; generalizing the proven property
  extension into reusable modules; broader translations; maps/geocoding; saved searches, favorites,
  and alerts; agent/office profiles; portal syndication; tours/video; paid placement; blog/listing
  cross-links; and PostgreSQL full-text search beyond basic keyword filtering.

  Promote an item only with a concrete consumer, bounded acceptance criteria, and a fresh dependency
  and track assignment. Listing it does not authorize implementation or make it a launch blocker.
  Close the inventory only when its items have been promoted or explicitly dropped with rationale.

## Deferred constraints and references

The live [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md)
own deferred findings and their exact growth triggers. Do not duplicate those lists here. The
standing no-`teams`/third-updater scope, internal-only devtools decision, settled presence contracts,
and resource safeguards remain in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov`.
That test checks ticket/context coverage, valid track and horizon assignments, and acyclic
dependencies; it does not certify a release verdict. Release evidence belongs in the changelog.
