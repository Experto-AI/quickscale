# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Ticket context](v88_ticket_context.md) | [Changelog](../../CHANGELOG.md)

## Goal and release finish line

Ship the v88 hardening release with working generated-project writes and accepted retained
hardening. Then deliver the first useful property portal in a
project-owned extension, generalizing capabilities only after that project proves their value.

The v88 hardening release had a root-finalized green candidate and release aggregate before terminal
attestation exposed CSRF integration defects. A retained terminal-remediation commit corrected the
token bootstrap and duplicate-cookie implementation, tests, generated hashes, and status. The next
continuation corrected the stale shell assertion and built the real generated-browser harness, but
the harness stopped at a production CSRF origin mismatch before login and the actual `apiRequest`
mutation. The prior green aggregate is historical evidence for prior bytes; the retained work remains
below task and release tiers and is not merge-ready. Merge, release-note/version checks, tagging,
publishing, and deployment remain separate maintainer actions.
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

**Release recovery path: genuine browser HTTPS origin → real `apiRequest` proof → owning task tier →
fresh release validation.** The retained checkpoint records this path but grants no new implementation
authority. Its conditional release authority remains unspent. All tracks stay idle for v88; their
post-v88 assignments are future ownership, not release work.

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
remain historical evidence for the pre-remediation bytes only. The retained remediation is neither
task-tier accepted nor release-tested; it is not merge-ready.

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
- The retained SA160 checkpoint has unspent conditional authority for a fresh Docker-backed release
  attempt after its focused and task-tier gaps close and its exact candidate is independently reviewed.
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

### SA160 continuation checkpoint — align the browser origin before resuming release proof

  **State (checkpointed 2026-09-10): retained and unmerged on `wt-track1` at WIP commit
  `9d3a6bcae3f3700cf5a2bdf08e12aa0197f7bb88`; integration ref `v88` remains
  `5716dabfc9d2d90eda69fe62a934c36567e9ec16`.** This is a test-harness checkpoint, not an accepted
  product candidate. No Core task gate, release attempt, merge, publication, tag, or deployment ran.

  **Completed:** the earlier retained remediation still preserves the production HttpOnly CSRF cookie,
  masked shell token, Django-last duplicate-cookie behavior, both generated callers, and three rebound
  emission variants. This continuation corrected the stale React-theme assertion to the existing
  `get_token` render contract; its exact node passed with one test and no skips. It also replaced the
  manual-header server probe with a generated production browser harness covering strict install,
  migrate, cache-table creation, frontend type-check/build, collectstatic, credential creation,
  production server startup, an unproxied HTTPS-redirect control, secure-cookie calibration, omitted-
  header rejection, and the intended `OrgCreatePage` → `useCreateOrg` → `apiRequest` mutation. The
  bootstrap, build, server, and redirect stages passed; the positive browser path did not.

  **Pending:** choose and authorize a test-only browser-visible HTTPS or equivalent origin-alignment
  mechanism that preserves shipped redirect, Secure, HttpOnly, proxy, and CSRF semantics. Complete the
  existing positive browser assertions without injected session cookies or positive CSRF headers, then
  pass the exact focused node with no skip. After that, resume the never-dispatched same-fact phase,
  owning Core task tier, exact candidate binding/review, conditional release, and green-only status
  reconciliation. Conditional authority for `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` remains unspent
  and applies only after focused and `make test-unit -- --core` evidence plus immutable review are green.

  **Blocking:** Chromium browses `http://localhost` while `X-Forwarded-Proto: https` makes Django treat
  the request as secure. Django therefore rejects the login POST because its HTTPS good origin does not
  match the browser's HTTP Origin; no Secure authenticated `sessionid` is established, and shell-token,
  omitted-header, real `apiRequest`, 201, redirect, and persistence assertions remain unreachable. The
  focused browser node is red, the owning Core task tier is unrun, and release/merge acceptance remains
  prohibited until those conditions close.

  **Decisions needed:** the previous run explicitly chose to stop and checkpoint instead of authorizing
  the proposed test-only localhost TLS terminator. A future run must approve that bounded mechanism or
  another genuine browser/Django scheme-alignment design; trusted-origin overrides, injected cookies or
  CSRF headers, and weakened production security settings are not acceptable substitutes.

  **Remaining plan:** start from WIP commit `9d3a6bcae3f3700cf5a2bdf08e12aa0197f7bb88` and retain the
  accepted stale-assertion correction and existing browser harness. The reviewed five-phase authority
  was stored as `EV-6`: phase A is accepted; phase B halted on the origin mismatch; phases C, D, and E
  were never dispatched because they hard-depend on that proof. Adding an HTTPS/origin mechanism changes
  phase B's reviewed scope, so obtain a fresh reviewed plan rather than redispatching it. Once the repaired
  browser phase is accepted, C is the first resumable undispatched phase: run same-fact frontend/manifest/
  taxonomy/status checks, then D's `make test-unit -- --core`, root-bind and independently review one
  exact candidate, and only then run E's authorized release carrier. A complete green release may update
  all owning status documents, proceed through convergence and terminal attestation, and enter the
  serialized exact-chain merge. Red or no-verdict evidence stays unmerged under the current retry policy.

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
